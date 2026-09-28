"""View models for the Streamlit UI.

Pure presentation helpers: they normalise whatever the pipeline wrote into
disc-shaped objects the UI can render. No pipeline logic, no side effects.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────  LOADING  ──────────────────────────────

def load_outputs(output_dir: Path) -> Dict[str, Any]:
    """Read every JSON/MD artefact the emitter produced."""
    results: Dict[str, Any] = {}
    if not output_dir or not Path(output_dir).exists():
        return results
    for path in sorted(Path(output_dir).iterdir()):
        if not path.is_file():
            continue
        try:
            if path.suffix == ".json":
                results[path.stem] = json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix in (".md", ".txt"):
                results[path.stem] = path.read_text(encoding="utf-8")
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            results[path.stem] = path.read_text(encoding="utf-8", errors="replace")
    return results


# ──────────────────────────────  MODELS  ──────────────────────────────

@dataclass
class SegmentVM:
    order: int
    segment_id: str
    scene_id: str
    description: str
    source_in: str
    source_out: str
    duration_ms: int
    audio_type: str
    transition: str
    reason: str
    evidence: List[str]
    risk_flags: List[str]
    subtitle: str
    text_card: str
    voice_over: str

    @property
    def duration_s(self) -> float:
        return self.duration_ms / 1000.0


@dataclass
class TrailerVM:
    key: str
    trailer_id: str
    audience: str
    duration_seconds: float
    segment_count: int
    estimated_cost: float
    generated_at: str
    status: str
    promise_text: str
    tone: str
    arc: List[str]
    emotions: List[str]
    avoid: List[str]
    total_scenes: int
    episode_duration_ms: int
    key_events: List[Dict[str, Any]]
    emotional_arc: List[Dict[str, Any]]
    capability: Dict[str, Any]
    cost_ledger: Dict[str, Any]
    segments: List[SegmentVM] = field(default_factory=list)
    checks: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    approvals: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    # ── derived ──
    @property
    def verdict_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for check in self.checks:
            v = str(check.get("verdict", "PASS")).upper()
            counts[v] = counts.get(v, 0) + 1
        return counts

    @property
    def pass_rate(self) -> float:
        if not self.checks:
            return 0.0
        return 100.0 * self.verdict_counts.get("PASS", 0) / len(self.checks)

    @property
    def check_types(self) -> List[str]:
        seen: List[str] = []
        for check in self.checks:
            t = str(check.get("check_type", "other"))
            if t not in seen:
                seen.append(t)
        return seen

    @property
    def flagged_segments(self) -> List[SegmentVM]:
        return [s for s in self.segments if s.risk_flags]

    @property
    def budget_used_pct(self) -> float:
        limit = float(self.cost_ledger.get("budget_limit") or 0)
        return 0.0 if not limit else 100.0 * float(self.cost_ledger.get("total_cost") or 0) / limit


@dataclass
class FleetVM:
    trailers: List[TrailerVM] = field(default_factory=list)
    overall_status: str = "UNKNOWN"
    generated_at: str = ""
    episode_id: str = ""
    total_cost: float = 0.0
    budget_limit: float = 0.0
    budget_remaining: float = 0.0
    capability: Dict[str, Any] = field(default_factory=dict)
    report: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> int:
        return sum(1 for t in self.trailers if t.status == "PASS")

    @property
    def warned(self) -> int:
        return sum(1 for t in self.trailers if "WARN" in t.status)

    @property
    def failed(self) -> int:
        return sum(1 for t in self.trailers if t.status in ("FAIL", "REJECTED"))

    @property
    def total_duration(self) -> float:
        return sum(t.duration_seconds for t in self.trailers)

    @property
    def avg_pass_rate(self) -> float:
        return sum(t.pass_rate for t in self.trailers) / len(self.trailers) if self.trailers else 0.0

    @property
    def total_segments(self) -> int:
        return sum(t.segment_count for t in self.trailers)

    @property
    def capability_warnings(self) -> List[str]:
        return [w for w in self.capability.get("warnings", []) if isinstance(w, str) and w]


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(text).lower()).strip("_") or "audience"


def _segment(raw: Dict[str, Any], index: int) -> SegmentVM:
    src = raw.get("source", {}) or {}
    audio = raw.get("audio", {}) or {}
    return SegmentVM(
        order=int(raw.get("sequence_order", index) or 0),
        segment_id=str(raw.get("segment_id", f"segment_{index}")),
        scene_id=str(src.get("scene_id", "?")),
        description=str(src.get("scene_description", "")),
        source_in=str(src.get("source_in", "")),
        source_out=str(src.get("source_out", "")),
        duration_ms=int(src.get("duration_ms") or 0),
        audio_type=str(audio.get("type", "n/a")),
        transition=str(raw.get("transition", "cut")),
        reason=str(raw.get("creative_reason", "")),
        evidence=[str(e) for e in _as_list(raw.get("evidence"))],
        risk_flags=[str(f) for f in _as_list(raw.get("risk_flags"))],
        subtitle=str(raw.get("subtitle") or ""),
        text_card=str(raw.get("text_card") or ""),
        voice_over=str(raw.get("voice_over") or ""),
    )


def _is_trailer(payload: Any) -> bool:
    return isinstance(payload, dict) and {"edl", "creative_brief"} & set(payload.keys())


def build_fleet(results: Dict[str, Any]) -> FleetVM:
    """Build the fleet view-model from raw parsed output files."""
    fleet = FleetVM()

    for key, payload in results.items():
        if _is_trailer(payload):
            fleet.trailers.append(_trailer_vm(key, payload))

    fleet.trailers.sort(key=lambda t: t.audience)

    report = results.get("validation_report")
    if isinstance(report, dict):
        fleet.report = report
        fleet.overall_status = str(report.get("overall_status", "UNKNOWN"))
        fleet.generated_at = str(report.get("generated_at", ""))
        fleet.episode_id = str(report.get("episode_id", ""))
        ledger = report.get("cost_ledger", {}) or {}
        fleet.total_cost = float(ledger.get("total_cost") or 0.0)
        fleet.budget_limit = float(ledger.get("budget_limit") or 0.0)
        fleet.budget_remaining = float(ledger.get("budget_remaining") or 0.0)
        fleet.capability = report.get("capability_report", {}) or {}

    if fleet.trailers:
        first = fleet.trailers[0]
        if not fleet.generated_at:
            fleet.generated_at = first.generated_at
        if not fleet.capability:
            fleet.capability = first.capability
        if not fleet.budget_limit:
            fleet.budget_limit = float(first.cost_ledger.get("budget_limit") or 0.0)
        if not fleet.total_cost:
            fleet.total_cost = float(first.cost_ledger.get("total_cost") or 0.0)
        if not fleet.budget_remaining:
            fleet.budget_remaining = float(first.cost_ledger.get("budget_remaining") or 0.0)
        if not fleet.overall_status or fleet.overall_status == "UNKNOWN":
            fleet.overall_status = _rollup(fleet.trailers)
        if not fleet.episode_id:
            fleet.episode_id = "episode"

    return fleet


def _rollup(trailers: List[TrailerVM]) -> str:
    statuses = {t.status for t in trailers}
    if "FAIL" in statuses or "REJECTED" in statuses:
        return "FAIL"
    if "PASS_WITH_WARNINGS" in statuses or "WARN" in statuses:
        return "PASS_WITH_WARNINGS"
    return "PASS" if statuses else "UNKNOWN"


def _trailer_vm(key: str, payload: Dict[str, Any]) -> TrailerVM:
    brief = payload.get("creative_brief", {}) or {}
    promise = brief.get("audience_promise", {}) or {}
    story = brief.get("story_map_summary", {}) or {}
    meta = payload.get("metadata", {}) or {}
    validation = payload.get("validation_summary", {}) or {}

    return TrailerVM(
        key=key,
        trailer_id=str(meta.get("trailer_id") or brief.get("trailer_id") or key),
        audience=str(meta.get("audience") or brief.get("audience") or _slug(key)),
        duration_seconds=float(meta.get("duration_seconds") or 0.0),
        segment_count=int(meta.get("segment_count") or len(_as_list(payload.get("edl")))),
        estimated_cost=float(meta.get("estimated_cost") or 0.0),
        generated_at=str(meta.get("generated_at") or ""),
        status=str(validation.get("overall_status") or "UNKNOWN"),
        promise_text=str(promise.get("promise_text") or "—"),
        tone=str(promise.get("tone") or "—"),
        arc=[str(a) for a in _as_list(promise.get("narrative_arc"))],
        emotions=[str(e) for e in _as_list(promise.get("intended_emotions"))],
        avoid=[str(a) for a in _as_list(promise.get("avoid"))],
        total_scenes=int(story.get("total_scenes") or 0),
        episode_duration_ms=int(story.get("total_duration_ms") or 0),
        key_events=[e for e in _as_list(story.get("key_events")) if isinstance(e, dict)],
        emotional_arc=[e for e in _as_list(story.get("emotional_arc")) if isinstance(e, dict)],
        capability=brief.get("capability_mode", {}) or {},
        cost_ledger=meta.get("cost_ledger_summary", {}) or {},
        segments=[_segment(s, i) for i, s in enumerate(_as_list(payload.get("edl"))) if isinstance(s, dict)],
        checks=[c for c in _as_list(validation.get("checks")) if isinstance(c, dict)],
        warnings=[str(w) for w in _as_list(validation.get("warnings"))],
        failures=[str(f) for f in _as_list(validation.get("failures"))],
        approvals=[str(a) for a in _as_list(validation.get("human_approvals_required"))],
        raw=payload,
    )


# ──────────────────────────────  RUN HISTORY  ──────────────────────────────

def recent_run_dirs(limit: int = 8) -> List[Path]:
    """List past run output directories, newest first.

    The pipeline writes into ``<temp>/atd_run_*/outputs``. Recovering them lets
    the UI restore results after a browser refresh, which would otherwise
    clear session state.
    """
    import tempfile

    root = Path(tempfile.gettempdir())
    try:
        candidates = [p for p in root.glob("atd_run_*") if (p / "outputs").is_dir()]
    except OSError:
        return []
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [p / "outputs" for p in candidates[:limit]]


def describe_run(path: Path) -> str:
    """Short human label for a run directory, e.g. ``14:32 · 3 trailers``."""
    import time

    fleet = build_fleet(load_outputs(path))
    stamp = time.strftime("%H:%M", time.localtime(Path(path).parent.stat().st_mtime))
    if not fleet.trailers:
        return f"{stamp} · empty"
    return f"{stamp} · {len(fleet.trailers)} trailers · {fleet.overall_status.replace('_',' ').lower()}"


# ──────────────────────────────  CLI INVOCATION  ──────────────────────────────

#: Input keys that map onto a CLI flag, in the order the CLI declares them.
INPUT_FLAGS = [
    ("scenes", "--scenes"),
    ("dialogue", "--dialogue"),
    ("policies", "--policies"),
    ("contracts", "--contracts"),
    ("audiences", "--audiences"),
    ("history", "--history"),
    ("costs", "--costs"),
]


def build_cli(
    python: str,
    config_path: Path,
    package_path: Path,
    output_dir: Path,
    use_mock: bool = True,
    optional: Optional[Dict[str, Path]] = None,
    render_video: bool = False,
    video_codec: str = "libx264",
    video_crf: int = 23,
    video_preset: str = "medium",
) -> List[str]:
    """Assemble the `python -m src.cli …` command line.

    ``--config`` and ``--mock`` are Click *group* options, so they must be
    placed between the module path and the ``run`` subcommand. Passing them
    after ``run`` makes Click abort with "No such option".
    """
    cmd = [python, "-m", "src.cli", "--config", str(config_path)]
    if use_mock:
        cmd.append("--mock")
    cmd += ["run", "--package", str(package_path), "--output", str(output_dir)]
    for key, flag in INPUT_FLAGS:
        path = (optional or {}).get(key)
        if path:
            cmd += [flag, str(path)]
    if render_video:
        cmd.append("--render-video")
        cmd += ["--video-codec", video_codec]
        cmd += ["--video-crf", str(video_crf)]
        cmd += ["--video-preset", video_preset]
    return cmd


def build_config(
    audiences: List[Dict[str, Any]],
    budget_usd: float,
    model_call_limit: int,
    media_processing_limit: int,
    min_duration: int,
    max_duration: int,
    min_segments: int,
    max_segments: int,
    diversity_threshold: float,
    late_episode_threshold: float,
    confidence_threshold: float,
    max_repair_iterations: int,
) -> Dict[str, Any]:
    """Map the sidebar controls onto the pipeline's config schema.

    Mirrors ``config/default_config.yaml`` exactly — the UI only supplies
    values, it never invents keys the pipeline does not read.
    """
    return {
        "audiences": audiences,
        "budget": {
            "total_usd": float(budget_usd),
            "model_call_limit": int(model_call_limit),
            "media_processing_limit": int(media_processing_limit),
            "warn_at_percent": 80,
        },
        "trailer": {
            "min_duration_seconds": int(min_duration),
            "max_duration_seconds": int(max_duration),
            "min_segments": int(min_segments),
            "max_segments": int(max_segments),
            "diversity_threshold": float(diversity_threshold),
        },
        "spoiler": {
            "late_episode_threshold": float(late_episode_threshold),
            "confidence_threshold": float(confidence_threshold),
        },
        "repair": {"max_iterations": int(max_repair_iterations), "escalation_on_failure": True},
    }


def stage_inputs(
    inputs: Path,
    package_name: str,
    package_bytes: bytes,
    optional: Optional[Dict[str, Tuple[str, bytes]]] = None,
) -> Dict[str, Path]:
    """Write uploads to disk; unzip the package when it is a .zip.

    Returns a mapping of input key → path on disk, ready for ``build_cli``.
    """
    import io
    import zipfile

    inputs = Path(inputs)
    inputs.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Path] = {}

    if package_name.lower().endswith(".zip"):
        package_dir = inputs / "episode_package"
        with zipfile.ZipFile(io.BytesIO(package_bytes)) as zf:
            zf.extractall(package_dir)
        paths["package"] = package_dir
    else:
        target = inputs / Path(package_name).name
        target.write_bytes(package_bytes)
        paths["package"] = target

    for key, (name, data) in (optional or {}).items():
        target = inputs / f"{key}{Path(name).suffix}"
        target.write_bytes(data)
        paths[key] = target

    return paths


# ──────────────────────────────  PIPELINE STAGES  ──────────────────────────────

STAGES = [
    ("Ingest & Quarantine", "Adapters parse inputs, injections neutralised"),
    ("Story Map", "Canonical scenes, entities, events, arc"),
    ("Spoiler Map", "3-layer detection with evidence"),
    ("Constraint Compilation", "Policies + contracts → rule DSL"),
    ("Audience Strategy", "Promise locked before clip selection"),
    ("Candidate Generation", "Arc-structured picks + diversity"),
    ("Independent Verification", "Deterministic first, LLM judges second"),
    ("Repair / Reject", "Targeted fix, max N iterations"),
    ("EDL Emission", "Trailer plans + validation report"),
]

DOCS = [
    ("🏛️", "Architecture", "ARCHITECTURE.md"),
    ("🤝", "AI Collaboration", "AI_COLLABORATION.md"),
    ("⚠️", "Known Limitations", "KNOWN_LIMITATIONS.md"),
    ("📘", "Readme", "README.md"),
]
