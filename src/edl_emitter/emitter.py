"""EDL emitter - outputs creative brief and EDL per trailer."""

from __future__ import annotations

import json
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.models.trailer import TrailerPlan, TrailerValidation, ValidationStatus
from src.models.story_map import StoryMap
from src.models.capability import CapabilityReport
from src.models.cost import CostLedger
from src.video_renderer import VideoRenderer, VideoRendererConfig


@dataclass
class EDLOutput:
    """Complete EDL output for a trailer."""
    creative_brief: dict
    edl: list[dict]
    validation_summary: dict
    metadata: dict


class EDLEmitter:
    """Emits EDL and creative brief in required JSON format."""

    def __init__(
        self, 
        output_dir: Path,
        source_video: Optional[Path] = None,
        render_video: bool = False,
        video_config: Optional[VideoRendererConfig] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.source_video = Path(source_video) if source_video else None
        self.render_video = render_video and self.source_video is not None
        self.video_config = video_config or VideoRendererConfig()
        self._video_renderer = VideoRenderer(self.video_config) if self.render_video else None

    def emit_trailer(
        self,
        trailer: TrailerPlan,
        story_map: StoryMap,
        capability_report: CapabilityReport,
        cost_ledger: CostLedger,
        decision_log: list[dict] | None = None,
    ) -> EDLOutput:
        """Emit complete output for a single trailer."""
        # Creative brief
        creative_brief = self._build_creative_brief(trailer, story_map, capability_report)
        
        # EDL (Edit Decision List)
        edl = self._build_edl(trailer, story_map)
        
        # Validation summary
        validation_summary = self._build_validation_summary(trailer.validation)
        
        # Metadata
        metadata = {
            "trailer_id": trailer.trailer_id,
            "audience": trailer.audience,
            "generated_at": datetime.now().isoformat(),
            "duration_seconds": trailer.duration_seconds,
            "segment_count": len(trailer.segments),
            "estimated_cost": trailer.estimated_cost,
            "capability_report": capability_report.model_dump() if hasattr(capability_report, 'model_dump') else {},
            "cost_ledger_summary": {
                "total_cost": cost_ledger.total_cost,
                "budget_limit": cost_ledger.budget_limit,
                "budget_remaining": cost_ledger.budget_remaining,
            },
        }
        
        output = EDLOutput(
            creative_brief=creative_brief,
            edl=edl,
            validation_summary=validation_summary,
            metadata=metadata,
        )
        
        # Write to file
        self._write_output(trailer.trailer_id, output)
        
        return output

    def emit_all(
        self,
        trailers: list[TrailerPlan],
        story_map: StoryMap,
        capability_report: CapabilityReport,
        cost_ledger: CostLedger,
        decision_log: list[dict] | None = None,
    ) -> list[EDLOutput]:
        """Emit outputs for all trailers."""
        outputs = []
        video_results = []
        
        for trailer in trailers:
            output = self.emit_trailer(trailer, story_map, capability_report, cost_ledger, decision_log)
            outputs.append(output)
            
            # Render video if enabled
            if self.render_video and self._video_renderer:
                try:
                    video_output = self.output_dir / f"{trailer.trailer_id}.mp4"
                    result = self._video_renderer.render_trailer(
                        trailer, story_map, self.source_video, video_output
                    )
                    video_results.append(result)
                except Exception as e:
                    video_results.append({
                        "trailer_id": trailer.trailer_id,
                        "error": str(e),
                        "output_path": str(self.output_dir / f"{trailer.trailer_id}.mp4"),
                    })
        
        # Write summary report
        self._write_summary(trailers, story_map, capability_report, cost_ledger, video_results)
        
        return outputs

    def _build_creative_brief(
        self, 
        trailer: TrailerPlan, 
        story_map: StoryMap, 
        capability_report: CapabilityReport
    ) -> dict:
        """Build creative brief from trailer plan."""
        promise = trailer.audience_promise
        
        return {
            "trailer_id": trailer.trailer_id,
            "audience": trailer.audience,
            "audience_promise": {
                "promise_text": promise.promise_text,
                "intended_emotions": promise.intended_emotions,
                "narrative_arc": promise.narrative_arc,
                "tone": promise.tone,
                "avoid": promise.avoid,
                "evidence": promise.evidence,
            },
            "story_map_summary": {
                "episode_id": story_map.episode_id,
                "total_scenes": len(story_map.scenes),
                "total_duration_ms": story_map.total_duration_ms,
                "key_events": [
                    {
                        "event_id": e.event_id,
                        "type": e.event_type,
                        "description": e.description[:200],
                        "scene": e.scene_id,
                        "position": e.normalised_position,
                    }
                    for e in story_map.major_events[:5]
                ],
                "emotional_arc": [
                    {"scene": b.scene_id, "emotion": b.emotion, "intensity": b.intensity}
                    for b in story_map.emotional_arc[:10]
                ],
            },
            "capability_mode": {
                "video": capability_report.has_video,
                "audio": capability_report.has_audio,
                "scene_descriptions": capability_report.has_scene_descriptions,
                "source_dialogue": capability_report.has_source_dialogue,
                "dialect_tracks": capability_report.dialect_tracks,
                "degraded_checks": capability_report.degraded_checks,
            },
        }

    def _build_edl(self, trailer: TrailerPlan, story_map: StoryMap) -> list[dict]:
        """Build Edit Decision List."""
        edl = []
        scene_map = {s.scene_id: s for s in story_map.scenes}
        
        for segment in trailer.segments:
            scene = scene_map.get(segment.video)
            
            edl_entry = {
                "segment_id": segment.segment_id,
                "sequence_order": segment.sequence_order,
                "source": {
                    "scene_id": segment.video,
                    "scene_description": scene.description if scene else None,
                    "source_in": segment.source_in.to_srt(),
                    "source_out": segment.source_out.to_srt(),
                    "source_in_ms": segment.source_in.normalised_ms,
                    "source_out_ms": segment.source_out.normalised_ms,
                    "duration_ms": segment.duration_ms,
                },
                "audio": {
                    "type": segment.audio,
                    "track_id": segment.audio if segment.audio not in ("dialogue", "music", "dialogue_and_music", "silence") else None,
                },
                "subtitle": segment.subtitle,
                "text_card": segment.text_card,
                "voice_over": segment.voice_over,
                "transition": segment.transition.value if segment.transition else "cut",
                "creative_reason": segment.reason,
                "evidence": segment.evidence,
                "risk_flags": segment.risk_flags,
            }
            edl.append(edl_entry)
        
        return edl

    def _build_validation_summary(self, validation: TrailerValidation | None) -> dict:
        """Build validation summary."""
        if not validation:
            return {"status": "NOT_VALIDATED", "checks": []}
        
        return {
            "overall_status": validation.status.value,
            "checks": [
                {
                    "check_id": c.check_id,
                    "check_type": c.check_type,
                    "verdict": c.verdict,
                    "evidence": c.evidence,
                    "details": c.details,
                }
                for c in validation.checks
            ],
            "warnings": validation.warnings,
            "failures": validation.failures,
            "human_approvals_required": validation.human_approvals_required,
        }

    def _write_output(self, trailer_id: str, output: EDLOutput) -> None:
        """Write output to JSON file."""
        output_file = self.output_dir / f"{trailer_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "creative_brief": output.creative_brief,
                "edl": output.edl,
                "validation_summary": output.validation_summary,
                "metadata": output.metadata,
            }, f, indent=2, ensure_ascii=False)

    def _write_summary(
        self,
        trailers: list[TrailerPlan],
        story_map: StoryMap,
        capability_report: CapabilityReport,
        cost_ledger: CostLedger,
        video_results: list[dict] | None = None,
    ) -> None:
        """Write summary report."""
        video_results = video_results or []
        video_by_id = {v.get("trailer_id") or v.get("output_path", "").split("/")[-1].split(".")[0]: v for v in video_results}
        
        summary = {
            "generated_at": datetime.now().isoformat(),
            "episode_id": story_map.episode_id,
            "trailers": [
                {
                    "trailer_id": t.trailer_id,
                    "audience": t.audience,
                    "status": t.validation.status.value if t.validation else "PENDING",
                    "duration_seconds": t.duration_seconds,
                    "segments": len(t.segments),
                    "estimated_cost": t.estimated_cost,
                    "video": video_by_id.get(t.trailer_id, {}),
                }
                for t in trailers
            ],
            "overall_status": "PASS" if all(
                t.validation and t.validation.status in (ValidationStatus.PASS, ValidationStatus.PASS_WITH_WARNINGS)
                for t in trailers
            ) else "FAIL",
            "cost_ledger": {
                "total_cost": cost_ledger.total_cost,
                "budget_limit": cost_ledger.budget_limit,
                "budget_remaining": cost_ledger.budget_remaining,
                "entries": [
                    {
                        "operation": e.operation,
                        "provider": e.provider,
                        "tokens_in": e.tokens_in,
                        "tokens_out": e.tokens_out,
                        "cost": e.cost,
                        "budget_tag": e.budget_tag,
                    }
                    for e in cost_ledger.entries
                ],
            },
            "capability_report": capability_report.model_dump() if hasattr(capability_report, 'model_dump') else {},
        }
        
        summary_file = self.output_dir / "validation_report.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)