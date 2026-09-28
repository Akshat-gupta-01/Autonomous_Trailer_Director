"""Main pipeline orchestrator."""

from __future__ import annotations

from typing import Optional
from dataclasses import dataclass
from pathlib import Path

from src.quarantine import QuarantineGate
from src.models.capability import CapabilityReport
from src.models.story_map import StoryMap
from src.models.spoiler import SpoilerFact
from src.models.rule import Rule
from src.models.audience import AudienceDefinition, AudiencePromise
from src.models.trailer import TrailerPlan, ValidationStatus
from src.models.cost import CostLedger
from src.story_mapper import StoryMapper, StoryMapperResult
from src.spoiler_engine import SpoilerEngine
from src.rule_compiler import RuleCompiler, RuleEvaluator
from src.bias_auditor import BiasAuditor
from src.audience_strategist import AudienceStrategist
from src.generator import TrailerGenerator
from src.verifier import VerifierOrchestrator
from src.repair_engine import RepairEngine
from src.change_handler import ChangeHandler
from src.edl_emitter import EDLEmitter, EDLOutput
from src.video_renderer import VideoRendererConfig
from src.providers import ModelProvider, BudgetController
from src.logging import DecisionLogger
from src.human_registry import HumanRegistry


@dataclass
class PipelineResult:
    """Complete pipeline result."""
    story_map: StoryMap
    spoiler_facts: list[SpoilerFact]
    rules: list[Rule]
    audience_promises: list[AudiencePromise]
    trailers: list[TrailerPlan]
    capability_report: CapabilityReport
    cost_ledger: CostLedger
    decision_log: list[dict]
    human_approvals: list[dict]
    edl_outputs: list[EDLOutput]


class Pipeline:
    """Main pipeline orchestrator."""

    def __init__(
        self,
        model_provider: ModelProvider,
        budget_controller: BudgetController,
        config: dict,
        output_dir: Path,
        mock_mode: bool = False,
        render_video: bool = False,
        video_config: Optional[VideoRendererConfig] = None,
    ):
        self.model_provider = model_provider
        self.budget_controller = budget_controller
        self.config = config
        self.output_dir = output_dir
        self.mock_mode = mock_mode
        self.render_video = render_video
        self.video_config = video_config or VideoRendererConfig()
        
        # Initialize components
        self.quarantine = QuarantineGate()
        self.decision_logger = DecisionLogger()
        self.human_registry = HumanRegistry()
        
        self.story_mapper = StoryMapper(model_provider, self.quarantine)
        self.spoiler_engine = SpoilerEngine(model_provider)
        self.rule_compiler = RuleCompiler(model_provider, self.quarantine)
        self.rule_evaluator = RuleEvaluator()
        self.bias_auditor = BiasAuditor()
        self.audience_strategist = AudienceStrategist(model_provider, self.quarantine, self.bias_auditor)
        self.trailer_generator = TrailerGenerator(model_provider, self.rule_evaluator, self.decision_logger)
        self.verifier = VerifierOrchestrator(model_provider, self.rule_evaluator, self.decision_logger)
        self.repair_engine = RepairEngine(self.trailer_generator, self.verifier, self.decision_logger)
        self.change_handler = ChangeHandler(self.trailer_generator, self.verifier, self.repair_engine, self.decision_logger)
        # EDL emitter will be created per-run with source video
        self.edl_emitter = None

    def run(
        self,
        episode_package_path: Path,
        scene_descriptions_path: Path | None = None,
        dialogue_path: Path | None = None,
        policies_path: Path | None = None,
        contracts_path: Path | None = None,
        audience_profiles_path: Path | None = None,
        historic_data_path: Path | None = None,
        cost_sheet_path: Path | None = None,
    ) -> PipelineResult:
        """Run the full pipeline."""
        
        # 1. Ingest and normalize
        capability_report = self._ingest_and_normalize(
            episode_package_path, scene_descriptions_path, dialogue_path,
            policies_path, contracts_path, audience_profiles_path,
            historic_data_path, cost_sheet_path
        )
        
        # 2. Build story map
        story_map_result = self._build_story_map(capability_report)
        story_map = story_map_result.story_map
        
        # 3. Build spoiler map
        spoiler_facts = self.spoiler_engine.build_spoiler_map(story_map)
        
        # 4. Compile rules
        rules = self._compile_rules(policies_path, contracts_path, capability_report)
        
        # 5. Initialize dependency graph
        # (will be done after first trailer generation)
        
        # 6. Plan audience promises
        audiences = self._load_audiences(audience_profiles_path)
        strategist_result = self.audience_strategist.plan_promises(
            audiences, story_map, spoiler_facts, capability_report
        )
        
        # 7. Generate trailers
        trailers = []
        for promise in strategist_result.promises:
            gen_result = self.trailer_generator.generate(
                promise, story_map, spoiler_facts, rules, capability_report, trailers
            )
            trailer = gen_result.trailer_plan
            
            # 8. Verify
            verification = self.verifier.verify(
                trailer, story_map, spoiler_facts, rules, capability_report
            )
            trailer.validation = verification.validation
            
            # 9. Repair if needed
            if trailer.validation.status == ValidationStatus.FAIL:
                repair_result = self.repair_engine.repair(
                    trailer, story_map, spoiler_facts, rules, capability_report
                )
                trailer = repair_result.trailer
            
            trailers.append(trailer)
        
        # 10. Initialize dependency graph with results
        self.change_handler.initialize_graph(story_map, spoiler_facts, rules, trailers)
        
        # 11. Emit EDLs (and optionally render videos)
        # Find source video file
        source_video = self._find_source_video(episode_package_path)
        
        self.edl_emitter = EDLEmitter(
            self.output_dir,
            source_video=source_video,
            render_video=self.render_video,
            video_config=self.video_config,
        )
        
        edl_outputs = self.edl_emitter.emit_all(
            trailers, story_map, capability_report, self.budget_controller.get_ledger()
        )
        
        return PipelineResult(
            story_map=story_map,
            spoiler_facts=spoiler_facts,
            rules=rules,
            audience_promises=strategist_result.promises,
            trailers=trailers,
            capability_report=capability_report,
            cost_ledger=self.budget_controller.get_ledger(),
            decision_log=self.decision_logger.export_json(),
            human_approvals=self.human_registry.export_json(),
            edl_outputs=edl_outputs,
        )

    def _ingest_and_normalize(
        self,
        episode_package_path: Path,
        scene_descriptions_path: Path | None,
        dialogue_path: Path | None,
        policies_path: Path | None,
        contracts_path: Path | None,
        audience_profiles_path: Path | None,
        historic_data_path: Path | None,
        cost_sheet_path: Path | None,
    ) -> CapabilityReport:
        """Ingest all input materials and build capability report."""
        warnings = []
        
        # Check episode package (required)
        has_video = episode_package_path.exists()
        if not has_video:
            warnings.append("No episode package found - text-only mode")
        
        # Check other materials
        has_scene_descriptions = scene_descriptions_path is not None and scene_descriptions_path.exists()
        has_source_dialogue = dialogue_path is not None and dialogue_path.exists()
        has_policies = policies_path is not None and policies_path.exists()
        has_contracts = contracts_path is not None and contracts_path.exists()
        has_audience_profiles = audience_profiles_path is not None and audience_profiles_path.exists()
        has_historic_data = historic_data_path is not None and historic_data_path.exists()
        has_cost_sheet = cost_sheet_path is not None and cost_sheet_path.exists()
        
        if not has_scene_descriptions:
            warnings.append("No scene descriptions - creative quality degraded")
        if not has_source_dialogue:
            warnings.append("No source dialogue - dialect drift check disabled")
        if not has_policies:
            warnings.append("No rating policies - using maximally restrictive defaults")
        if not has_contracts:
            warnings.append("No contracts - all asset use denied by default")
        if not has_audience_profiles:
            warnings.append("No audience profiles - using generic strategy")
        
        # Extract dialect tracks from dialogue if available
        dialect_tracks = []
        if has_source_dialogue:
            # Would parse dialogue files to find language tracks
            dialect_tracks = ["hi"]  # Placeholder
        
        return CapabilityReport(
            has_video=has_video,
            has_audio=has_video,  # Assume video has audio
            has_scene_descriptions=has_scene_descriptions,
            has_source_dialogue=has_source_dialogue,
            dialect_tracks=dialect_tracks,
            has_policies=has_policies,
            has_contracts=has_contracts,
            has_audience_profiles=has_audience_profiles,
            has_historic_data=has_historic_data,
            has_cost_sheet=has_cost_sheet,
            warnings=warnings,
            degraded_checks=[
                "dialect_drift" if not has_source_dialogue else "",
                "visual_analysis" if not has_video else "",
            ],
        )

    def _build_story_map(self, capability_report: CapabilityReport) -> StoryMapperResult:
        """Build story map from ingested materials."""
        # Parse scenes from episode package
        scenes = self._parse_scenes()
        
        # Parse entities
        entities = self._parse_entities()
        
        # Parse dialogue by scene
        dialogue_by_scene = self._parse_dialogue_by_scene()
        
        # Parse scene descriptions
        scene_descriptions = self._parse_scene_descriptions()
        
        return self.story_mapper.build_story_map(
            scenes, entities, dialogue_by_scene, scene_descriptions, capability_report
        )

    def _compile_rules(
        self, 
        policies_path: Path | None, 
        contracts_path: Path | None,
        capability_report: CapabilityReport,
    ) -> list[Rule]:
        """Compile rules from policies and contracts."""
        all_rules = []
        
        if policies_path and policies_path.exists():
            policy_text = policies_path.read_text(encoding="utf-8")
            policy_rules = self.rule_compiler.compile_policies([("policy_main", policy_text)], capability_report)
            all_rules.extend(policy_rules)
        
        if contracts_path and contracts_path.exists():
            contract_text = contracts_path.read_text(encoding="utf-8")
            contract_rules = self.rule_compiler.compile_contracts([("contract_main", contract_text)], capability_report)
            all_rules.extend(contract_rules)
        
        # If no policies/contracts, apply conservative defaults
        if not all_rules:
            capability_report.warnings.append("No rules compiled - using conservative defaults")
            # Add default deny-all rules would go here
        
        return all_rules

    def _load_audiences(self, audience_profiles_path: Path | None) -> list[AudienceDefinition]:
        """Load audience definitions."""
        if audience_profiles_path and audience_profiles_path.exists():
            import json
            with open(audience_profiles_path) as f:
                data = json.load(f)
            if isinstance(data, list):
                return [AudienceDefinition(**a) for a in data]
        
        # Return default audiences from config
        return [AudienceDefinition(**a) for a in self.config.get("audiences", [])]

    def _find_source_video(self, episode_package_path: Path) -> Optional[Path]:
        """Find the source video file in the episode package."""
        video_extensions = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v"}
        
        if episode_package_path.is_file() and episode_package_path.suffix.lower() in video_extensions:
            return episode_package_path
        
        if episode_package_path.is_dir():
            # Search for video files in directory
            for ext in video_extensions:
                videos = list(episode_package_path.rglob(f"*{ext}"))
                if videos:
                    return videos[0]  # Return first video found
        
        return None

    def _parse_scenes(self) -> list:
        """Parse scenes from episode package."""
        # Placeholder - would use adapters
        from src.models.scene import Scene
        from src.models.timecode import TimecodeFormat, ms_to_timecode
        return [
            Scene(
                scene_id=f"scene_{i:02d}",
                timecode_in=ms_to_timecode(i*30000, TimecodeFormat.MILLISECONDS),
                timecode_out=ms_to_timecode((i+1)*30000, TimecodeFormat.MILLISECONDS),
                duration_ms=30000,
                description=f"Scene {i} description",
                entities=[f"char_{i}"],
                content_tags=[],
                is_characterised=True,
            )
            for i in range(8)
        ]

    def _parse_entities(self) -> list:
        """Parse entities."""
        from src.models.scene import Entity, EntityType
        return [
            Entity(entity_id=f"char_{i}", entity_type=EntityType.CHARACTER, name=f"Character {i}")
            for i in range(4)
        ]

    def _parse_dialogue_by_scene(self) -> dict:
        """Parse dialogue grouped by scene."""
        return {}

    def _parse_scene_descriptions(self) -> dict:
        """Parse scene descriptions."""
        return {}


