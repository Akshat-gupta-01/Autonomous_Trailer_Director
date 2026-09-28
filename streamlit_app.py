#!/usr/bin/env python
"""
Streamlit Web Interface for Autonomous Trailer Director
Run with: streamlit run streamlit_app.py

This module is presentation-only. All planning / verification logic stays in
``src/`` and is invoked through the unchanged ``python -m src.cli`` entry point.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import ui_theme as ui  # noqa: E402
import ui_viewmodels as vm  # noqa: E402

st.set_page_config(
    page_title="Trailer Director Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"about": "Autonomous Trailer Director · OTT Dialect Platform"},
)

# ═══════════════════════════════  SESSION STATE  ═══════════════════════════════

DEFAULTS: Dict[str, Any] = {
    "theme": "dark",
    "pipeline_results": None,
    "run_logs": "",
    "output_dir": None,
    "active_view": "studio",
    "run_count": 0,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Force dark theme - no toggle
theme = "dark"
st.session_state["theme"] = "dark"

# ═══════════════════════════════  STYLES  ═══════════════════════════════

st.markdown(ui.build_css(theme), unsafe_allow_html=True)

NAV = [
    ("studio", "🎛️ Studio"),
    ("results", "🎞️ Results"),
    ("validation", "🛡️ Validate"),
    ("insights", "📊 Insights"),
    ("docs", "📖 Docs"),
]


def go(view: str) -> None:
    """Switch the main view without a full page reload."""
    st.session_state["active_view"] = view


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


# ═══════════════════════════════  SIDEBAR  ═══════════════════════════════

DEFAULT_AUDIENCES = [
    {
        "audience_id": "family",
        "name": "Family viewers",
        "description": "General family audience seeking wholesome entertainment",
        "goal": "Communicate warmth, stakes and broad entertainment value",
        "special_care": ["Follow the strictest rating rules", "Avoid frightening or suggestive context"],
        "rating_policy_ids": ["policy_family"],
        "age_range": [0, 100],
        "territories": ["IN", "US", "GB"],
        "languages": ["en", "hi"],
    },
    {
        "audience_id": "young_adult",
        "name": "Young adult viewers",
        "description": "Young adult audience seeking engaging character-driven stories",
        "goal": "Highlight pace, humour, identity and character conflict",
        "special_care": ["Do not use misleading intensity", "Do not reveal the central twist"],
        "rating_policy_ids": ["policy_young_adult"],
        "age_range": [16, 30],
        "territories": ["IN", "US", "GB"],
        "languages": ["en", "hi"],
    },
    {
        "audience_id": "dialect_region",
        "name": "Dialect-region viewers",
        "description": "Hindi dialect-speaking regional audience",
        "goal": "Show that the release understands their language and cultural context",
        "special_care": ["Do not reduce the audience to stereotypes", "Do not treat dialect as a comic device"],
        "rating_policy_ids": ["policy_dialect_region"],
        "age_range": [18, 60],
        "territories": ["IN"],
        "languages": ["hi"],
    },
]

PRESETS = {
    "Balanced (recommended)": {
        "total_usd": 10.0, "model_call_limit": 200, "media_processing_limit": 50,
        "min_duration": 20, "max_duration": 60, "min_segments": 3, "max_segments": 12,
        "diversity_threshold": 0.4, "late_episode_threshold": 0.7,
        "confidence_threshold": 0.6, "max_repair_iterations": 3,
    },
    "Compliance-first": {
        "total_usd": 20.0, "model_call_limit": 320, "media_processing_limit": 80,
        "min_duration": 20, "max_duration": 45, "min_segments": 4, "max_segments": 9,
        "diversity_threshold": 0.55, "late_episode_threshold": 0.55,
        "confidence_threshold": 0.4, "max_repair_iterations": 5,
    },
    "Creative-max": {
        "total_usd": 15.0, "model_call_limit": 400, "media_processing_limit": 120,
        "min_duration": 30, "max_duration": 90, "min_segments": 5, "max_segments": 16,
        "diversity_threshold": 0.25, "late_episode_threshold": 0.8,
        "confidence_threshold": 0.75, "max_repair_iterations": 3,
    },
    "Fast / cheap": {
        "total_usd": 3.0, "model_call_limit": 60, "media_processing_limit": 20,
        "min_duration": 15, "max_duration": 40, "min_segments": 3, "max_segments": 6,
        "diversity_threshold": 0.35, "late_episode_threshold": 0.7,
        "confidence_threshold": 0.7, "max_repair_iterations": 1,
    },
}

FILE_SPECS = [
    ("package", "📦", "Episode Package", ["mp4", "mkv", "mov", "json", "zip"], "Video, clip folder (zip) or JSON manifest", True),
    ("scenes", "🎞️", "Scene Descriptions", ["json", "csv", "txt", "md", "pdf"], "Scene breakdowns in any supported format", False),
    ("dialogue", "💬", "Dialogue & Subtitles", ["srt", "vtt", "ass", "json", "csv"], "Subtitle tracks for dialogue grounding", False),
    ("policies", "⚖️", "Rating Policies", ["json", "yaml", "yml", "pdf", "txt"], "Content rating policies per territory", False),
    ("contracts", "📜", "Contracts", ["json", "yaml", "yml", "pdf", "txt"], "Actor, music and territory rights", False),
    ("audiences", "👥", "Audience Profiles", ["json", "csv", "yaml", "yml"], "Overrides the audience editor below", False),
    ("history", "📈", "Historic Performance", ["json", "csv"], "Past engagement signals (optional)", False),
    ("costs", "💵", "Cost Sheet", ["json", "yaml", "yml", "csv"], "Operation cost definitions (optional)", False),
]

with st.sidebar:
    brand = st.container()
    with brand:
        html(f"""
        <div style="display:flex;align-items:center;gap:.65rem;margin-bottom:.2rem">
          <div style="width:38px;height:38px;border-radius:11px;display:grid;place-items:center;font-size:1.15rem;
               background:linear-gradient(135deg,{ui.t('dark','accent')},{ui.t('dark','accent2')});">🎬</div>
          <div>
            <div style="font-weight:800;font-size:1.02rem;line-height:1.15">Trailer Director</div>
            <div style="font-size:.66rem;color:var(--muted);letter-spacing:.14em;text-transform:uppercase">
              Autonomous studio v{ui.UI_VERSION}</div>
          </div>
        </div>""")

    # API Key loaded from environment only (not shown in UI)
    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    html(ui.badge("Live mode" if has_key else "Mock mode", "ok" if has_key else "warn", "dark"))

    st.divider()

    preset = st.selectbox("⚡ Preset", list(PRESETS), help="Fills every control below. Existing values are replaced.")

    with st.expander("💰 Budget & limits", expanded=False):
        p = PRESETS[preset]
        budget_usd = st.number_input("Total budget (USD)", 0.01, 100.0, float(p["total_usd"]), 0.5)
        model_call_limit = st.number_input("Model call limit", 10, 1000, int(p["model_call_limit"]), 10)
        media_processing_limit = st.number_input("Media processing limit", 5, 200, int(p["media_processing_limit"]), 5)

    with st.expander("🎥 Trailer constraints", expanded=True):
        p = PRESETS[preset]
        c1, c2 = st.columns(2)
        with c1:
            min_duration = st.number_input("Min seconds", 10, 120, int(p["min_duration"]))
        with c2:
            max_duration = st.number_input("Max seconds", 20, 300, int(p["max_duration"]))
        c3, c4 = st.columns(2)
        with c3:
            min_segments = st.number_input("Min segments", 1, 20, int(p["min_segments"]))
        with c4:
            max_segments = st.number_input("Max segments", 3, 30, int(p["max_segments"]))
        diversity_threshold = st.slider("Diversity (Jaccard)", 0.0, 1.0, float(p["diversity_threshold"]), 0.05)

    with st.expander("🚫 Spoiler guard", expanded=False):
        p = PRESETS[preset]
        late_episode_threshold = st.slider("Late-episode threshold", 0.0, 1.0, float(p["late_episode_threshold"]), 0.05)
        confidence_threshold = st.slider("Confidence threshold", 0.0, 1.0, float(p["confidence_threshold"]), 0.05)

    with st.expander("🔧 Repair engine", expanded=False):
        max_repair_iterations = st.number_input("Max repair iterations", 1, 10, int(PRESETS[preset]["max_repair_iterations"]))

    with st.expander("🎬 Video rendering", expanded=False):
        render_video = st.checkbox("Render actual video files", value=False, help="Requires ffmpeg installed on the system")
        if render_video:
            vcol1, vcol2 = st.columns(2)
            with vcol1:
                video_codec = st.selectbox("Video codec", ["libx264", "libx265", "libvpx-vp9"], index=0)
                video_preset = st.selectbox("Preset", ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"], index=5)
            with vcol2:
                video_crf = st.slider("CRF (quality)", 18, 28, 23, help="Lower = better quality, larger file")
                st.caption("⚠️ Requires ffmpeg in PATH")
        else:
            video_codec = "libx264"
            video_preset = "medium"
            video_crf = 23

    st.divider()
    st.markdown("**👥 Audiences**")
    audiences_json = st.text_area(
        "Audience definitions (JSON)",
        value=json.dumps(DEFAULT_AUDIENCES, indent=2),
        height=240,
        help="Edit as JSON — one object per audience.",
        label_visibility="collapsed",
    )
    audiences_error = None
    try:
        audiences = json.loads(audiences_json)
        if not isinstance(audiences, list) or not audiences:
            raise ValueError("Expected a non-empty list of audience objects")
    except (json.JSONDecodeError, ValueError) as exc:
        audiences_error = str(exc)
        audiences = DEFAULT_AUDIENCES

    if audiences_error:
        st.error(f"Audience JSON invalid — falling back to defaults. {audiences_error}")
    else:
        names = ", ".join(str(a.get("name", a.get("audience_id", "?"))) for a in audiences if isinstance(a, dict))
        st.caption(f"✅ {len(audiences)} audiences · {names}")

    st.divider()
    st.caption(f"UI v{ui.UI_VERSION} · pipeline untouched · Python {sys.version.split()[0]}")


# ═══════════════════════════════  HEADER / NAV  ═══════════════════════════════

fleet: Optional[vm.FleetVM] = None
if st.session_state["pipeline_results"]:
    fleet = vm.build_fleet(st.session_state["pipeline_results"])

fleet_status = fleet.overall_status if fleet else "NO RUN"
mode_label = "Live" if os.environ.get("GEMINI_API_KEY") else "Mock"
chips = [
    f"🧠 <b>{ui.esc(mode_label)}</b>",
    f"👥 <b>{len(audiences)}</b> audiences",
    f"⏱️ <b>{ui.esc(f'{fleet.total_duration:.0f}s' if fleet else '—')}</b> total runtime",
    f"🎬 <b>{ui.esc(len(fleet.trailers) if fleet else 0)}</b> plans",
    f"✅ {ui.status_badge(fleet_status, theme)}",
]

html(ui.hero(
    "OTT Dialect Platform · Creative Compliance Engine",
    "Autonomous Trailer Director",
    "Upload episode materials, lock audience strategy, then let the deterministic pipeline plan, verify and repair "
    "policy-compliant trailers for every audience in one pass.",
    chips,
))

nav_cols = st.columns(5, gap="small")
for col, (key, label) in zip(nav_cols, NAV):
    with col:
        disabled = key in ("results", "validation", "insights") and not fleet
        if st.button(
            label,
            key=f"nav_{key}",
            use_container_width=True,
            disabled=disabled,
            type="primary" if st.session_state["active_view"] == key else "secondary",
            help=f"Switch to the {key} view",
        ):
            go(key)

view = st.session_state["active_view"]
st.divider()


# ═══════════════════════════════  VIEW: STUDIO  ═══════════════════════════════

def render_studio() -> None:
    left, right = st.columns([1.32, 1], gap="large")

    with left:
        html(ui.section("Episode materials", "📥"))
        st.caption("Only the episode package is required. Everything else sharpens the plan.")

        required = st.container()
        with required:
            st.markdown("**Required**")
            episode_package = st.file_uploader(
                "Episode package",
                type=["mp4", "mkv", "mov", "json", "zip"],
                help="Video file, clip directory as .zip, or a JSON manifest",
                label_visibility="collapsed",
            )

        opt_left, opt_right = st.columns(2)
        uploads: Dict[str, Any] = {"package": episode_package}
        for col, specs in ((opt_left, FILE_SPECS[1:5]), (opt_right, FILE_SPECS[5:])):
            with col:
                st.markdown("**Optional**")
                for key, icon, label, types, help_text, _ in specs:
                    uploads[key] = st.file_uploader(
                        f"{icon} {label}",
                        type=types,
                        help=help_text,
                        label_visibility="collapsed",
                        key=f"up_{key}",
                    )
                    if uploads[key] is None:
                        st.caption(f"· {label} — {help_text}")

        with right:
            html(ui.section("Pipeline", "🧭"))
            st.caption("Pipeline stages run in order. Nothing here alters the engine — only its inputs.")

            html(ui.stages(vm.STAGES))

            run_col, reset_col = st.columns([2, 1])
            with run_col:
                run_clicked = st.button(
                    "🚀  Run Pipeline",
                    type="primary",
                    use_container_width=True,
                    disabled=episode_package is None,
                )
            with reset_col:
                if st.button("🧹  Clear", use_container_width=True, disabled=not st.session_state["pipeline_results"]):
                    st.session_state["pipeline_results"] = None
                    st.session_state["run_logs"] = ""
                    st.session_state["output_dir"] = None
                    st.session_state["run_count"] = 0
                    st.rerun()

            if episode_package is None:
                st.info("📎 Upload an episode package to unlock the Run button.")
            elif audiences_error:
                st.warning("⚠️ Fix the audience JSON or the run will use default audiences.")

            # Results live in session state, so a browser refresh clears them.
            # Previous runs are still on disk — offer to restore one.
            if not st.session_state["pipeline_results"]:
                history = vm.recent_run_dirs()
                if history:
                    st.write("")
                    labels = [vm.describe_run(d) for d in history]
                    pick = st.selectbox(
                        "Recent runs on this machine",
                        range(len(history)),
                        format_func=lambda i: labels[i],
                        key="history_pick",
                    )
                    if st.button("♻️  Restore this run", use_container_width=True):
                        st.session_state["pipeline_results"] = vm.load_outputs(history[pick])
                        st.session_state["output_dir"] = str(history[pick])
                        st.session_state["run_count"] += 1
                        go("results")
                        st.rerun()

            if st.session_state["run_logs"]:
                with st.expander("🧾 Last run log", expanded=False):
                    st.code(st.session_state["run_logs"][-6000:], language="bash")
    return run_clicked, episode_package, uploads


studio_result = render_studio() if view == "studio" else None


# ═══════════════════════════════  PIPELINE EXECUTION  ═══════════════════════════════

def execute_pipeline(package, uploads: Dict[str, Any], live_logs: bool, 
                     render_video: bool = False, video_codec: str = "libx264",
                     video_crf: int = 23, video_preset: str = "medium") -> bool:
    """Invoke the unchanged CLI pipeline and stream its output."""
    use_mock = not bool(os.environ.get("GEMINI_API_KEY"))
    run_dir = Path(tempfile.mkdtemp(prefix="atd_run_"))
    inputs = run_dir / "inputs"
    outputs = run_dir / "outputs"
    inputs.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    optional = {
        key: (uploads[key].name, uploads[key].getvalue())
        for key, _i, _l, _t, _h, _r in FILE_SPECS[1:]
        if uploads.get(key) is not None
    }
    paths = vm.stage_inputs(inputs, package.name, package.getvalue(), optional)

    import yaml

    config = vm.build_config(
        audiences=audiences,
        budget_usd=budget_usd,
        model_call_limit=model_call_limit,
        media_processing_limit=media_processing_limit,
        min_duration=min_duration,
        max_duration=max_duration,
        min_segments=min_segments,
        max_segments=max_segments,
        diversity_threshold=diversity_threshold,
        late_episode_threshold=late_episode_threshold,
        confidence_threshold=confidence_threshold,
        max_repair_iterations=max_repair_iterations,
    )
    config_path = inputs / "config.yaml"
    config_path.write_text(yaml.dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")

    cmd = vm.build_cli(
        python=sys.executable,
        config_path=config_path,
        package_path=paths["package"],
        output_dir=outputs,
        use_mock=use_mock,
        optional={k: v for k, v in paths.items() if k != "package"},
        render_video=render_video,
        video_codec=video_codec,
        video_crf=video_crf,
        video_preset=video_preset,
    )

    started = time.time()
    log_lines: List[str] = []
    process = subprocess.Popen(
        cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    for line in iter(process.stdout.readline, ""):
        log_lines.append(line.rstrip())
        if live_logs and st.session_state.get("_log_box"):
            st.session_state["_log_box"].code("\n".join(log_lines[-60:]) or "…", language="bash")
    process.wait()
    elapsed = time.time() - started

    st.session_state["run_logs"] = "\n".join(log_lines)
    if process.returncode != 0:
        st.error(f"Pipeline exited with code {process.returncode}")
        st.code("\n".join(log_lines[-80:]), language="bash")
        return False

    results = vm.load_outputs(outputs)
    if not results:
        st.error("Pipeline finished but produced no readable artefacts.")
        st.code("\n".join(log_lines[-80:]), language="bash")
        return False

    st.session_state["pipeline_results"] = results
    st.session_state["output_dir"] = str(outputs)
    st.session_state["run_count"] += 1
    st.session_state["last_elapsed"] = elapsed
    return True


if studio_result and studio_result[0] and studio_result[1] is not None:
    run_clicked, package, uploads = studio_result
    with st.status("Running the deterministic pipeline…", expanded=True) as status:
        st.write("Building inputs, invoking `python -m src.cli`, streaming logs.")
        st.session_state["_log_box"] = st.empty()
        try:
            ok = execute_pipeline(package, uploads, live_logs=True,
                                 render_video=render_video,
                                 video_codec=video_codec,
                                 video_crf=video_crf,
                                 video_preset=video_preset)
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            st.exception(exc)
            ok = False
        finally:
            st.session_state["_log_box"] = None

        if ok:
            new_fleet = vm.build_fleet(st.session_state["pipeline_results"])
            status.update(label=f"✅ Completed in {st.session_state.get('last_elapsed', 0):.1f}s", state="complete")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Trailers", len(new_fleet.trailers))
            c2.metric("Overall", new_fleet.overall_status.replace("_", " "))
            c3.metric("Runtime", f"{new_fleet.total_duration:.0f}s")
            c4.metric("Cost", f"${new_fleet.total_cost:.2f}")
            b1, b2, _ = st.columns([1, 1, 3])
            if b1.button("🎞️  View results", type="primary", use_container_width=True):
                go("results")
            if b2.button("🛡️  Validation", use_container_width=True):
                go("validation")
        else:
            status.update(label="❌ Pipeline failed", state="error")


# ═══════════════════════════════  VIEW: RESULTS  ═══════════════════════════════

def render_results() -> None:
    if not fleet:
        html(ui.empty_state("🎞️", "No results yet", "Run the pipeline from the Studio to generate trailer plans."))
        return

    html(ui.section("Fleet overview", "🎞️"))
    html(ui.kpi_row([
        ui.kpi("Trailers", str(len(fleet.trailers)), "one per audience"),
        ui.kpi("Total runtime", f"{fleet.total_duration:.0f}s", f"{fleet.total_segments} segments", ui.t(theme, "accent2")),
        ui.kpi("Compliance", f"{fleet.avg_pass_rate:.0f}%", "average check pass rate", ui.t(theme, "ok")),
        ui.kpi("Budget", f"${fleet.total_cost:.2f}", f"of ${fleet.budget_limit:.2f}", ui.t(theme, "warn")),
    ]))

    for index, trailer in enumerate(fleet.trailers):
        st.write("")
        head_l, head_r = st.columns([4, 1.2])
        with head_l:
            st.markdown(f"#### {index+1}. {trailer.audience.replace('_',' ').title()}")
        with head_r:
            st.markdown(
                f'<div style="text-align:right">{ui.status_badge(trailer.status, theme)}</div>',
                unsafe_allow_html=True,
            )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Duration", f"{trailer.duration_seconds:.0f}s")
        m2.metric("Segments", trailer.segment_count)
        m3.metric("Checks passed", f"{trailer.verdict_counts.get('PASS',0)}/{len(trailer.checks)}")
        m4.metric("Story scenes", trailer.total_scenes)

        st.markdown("**Cut timeline**")
        html(ui.timeline(_raw_segments(trailer), theme, trailer.arc))

        with st.expander("Creative brief & promise", expanded=False):
            b1, b2 = st.columns([1.5, 1])
            with b1:
                st.markdown("**Audience promise**")
                st.write(trailer.promise_text)
                st.markdown(f"**Tone** · `{trailer.tone}`")
                st.markdown("**Arc** · " + " → ".join(trailer.arc) if trailer.arc else "**Arc** · —")
            with b2:
                st.markdown("**Target emotions**")
                st.write(", ".join(trailer.emotions) or "—")
                st.markdown("**Must avoid**")
                for item in trailer.avoid:
                    st.markdown(f"· {item}")

        with st.expander("Edit decision list (EDL)", expanded=False):
            for seg in trailer.segments:
                flag = "⚠️" if seg.risk_flags else "✅"
                title = f"{flag} #{seg.order} · {seg.scene_id} · {seg.duration_s:.1f}s"
                with st.expander(title):
                    e1, e2, e3 = st.columns(3)
                    e1.metric("In → Out", f"{seg.source_in} → {seg.source_out}")
                    e2.metric("Audio", seg.audio_type)
                    e3.metric("Transition", seg.transition)
                    st.markdown(f"**Why this clip** — {seg.reason}")
                    if seg.description:
                        st.caption(seg.description)
                    if seg.subtitle:
                        st.markdown(f"**Subtitle** — {seg.subtitle}")
                    if seg.text_card:
                        st.markdown(f"**Text card** — {seg.text_card}")
                    if seg.voice_over:
                        st.markdown(f"**Voice-over** — {seg.voice_over}")
                    if seg.evidence:
                        st.caption("Evidence: " + " · ".join(seg.evidence))
                    if seg.risk_flags:
                        st.warning("Risk flags: " + ", ".join(seg.risk_flags))

        with st.expander("Raw JSON", expanded=False):
            st.json(trailer.raw, expanded=False)


def _raw_segments(trailer: vm.TrailerVM) -> List[Dict[str, Any]]:
    edl = trailer.raw.get("edl", [])
    return [e for e in edl if isinstance(e, dict)]


# ═══════════════════════════════  VIEW: VALIDATION  ═══════════════════════════════

def render_validation() -> None:
    if not fleet:
        html(ui.empty_state("🛡️", "Nothing to verify", "Run the pipeline to generate validation evidence."))
        return

    html(ui.section("Verification verdict", "🛡️"))
    top_l, top_r = st.columns([1, 2])
    with top_l:
        html(ui.card(f'<div style="text-align:center">{ui.status_badge(fleet.overall_status, theme)}</div>', accent=True))
    with top_r:
        counts: Dict[str, int] = {}
        for trailer in fleet.trailers:
            for verdict, n in trailer.verdict_counts.items():
                counts[verdict] = counts.get(verdict, 0) + n
        html(ui.card(ui.donut(list(counts.items()), theme, str(sum(counts.values())), "checks")))

    if fleet.capability_warnings:
        st.markdown("")
        with st.expander(f"⚠️ Capability degradation ({len(fleet.capability_warnings)})", expanded=True):
            for warning in fleet.capability_warnings:
                st.markdown(f"· {warning}")

    st.write("")
    for trailer in fleet.trailers:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:.6rem;margin:.9rem 0 .3rem">'
            f'<b>{ui.esc(trailer.audience.replace("_"," ").title())}</b>'
            f'{ui.status_badge(trailer.status, theme)}</div>',
            unsafe_allow_html=True,
        )
        f1, f2, f3 = st.columns([1, 1, 2])
        f1.metric("Pass rate", f"{trailer.pass_rate:.0f}%")
        f2.metric("WARN / FAIL", f"{trailer.verdict_counts.get('WARN',0)} / {trailer.verdict_counts.get('FAIL',0)}")
        f3.metric("Human approvals", len(trailer.approvals))

        if trailer.checks:
            verdict_filter = st.multiselect(
                "Filter verdicts",
                ["PASS", "WARN", "FAIL"],
                default=[],
                key=f"vf_{trailer.key}",
                placeholder="All verdicts",
            )
            type_filter = st.multiselect(
                "Filter check types",
                trailer.check_types,
                default=[],
                key=f"cf_{trailer.key}",
                placeholder="All check types",
            )
            rows = [
                {
                    "Check": c.get("check_id", ""),
                    "Type": c.get("check_type", ""),
                    "Verdict": c.get("verdict", ""),
                    "Details": str(c.get("details", ""))[:220],
                }
                for c in trailer.checks
                if (not verdict_filter or c.get("verdict") in verdict_filter)
                and (not type_filter or c.get("check_type") in type_filter)
            ]
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
            else:
                st.caption("No checks match the current filters.")

        for label, items, kind in (
            ("⚠️ Warnings", trailer.warnings, "warning"),
            ("❌ Failures", trailer.failures, "error"),
            ("👤 Human approvals required", trailer.approvals, "info"),
        ):
            if items:
                with st.expander(f"{label} ({len(items)})", expanded=True):
                    for item in items:
                        getattr(st, kind)(item)


# ═══════════════════════════════  VIEW: INSIGHTS  ═══════════════════════════════

def render_insights() -> None:
    if not fleet:
        html(ui.empty_state("📊", "No data to chart", "Run the pipeline first — charts populate automatically."))
        return

    html(ui.section("Comparative analytics", "📊"))
    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**Duration vs audience**")
        st.bar_chart(
            {t.audience: t.duration_seconds for t in fleet.trailers},
            horizontal=True,
        )
    with d2:
        st.markdown("**Clip reuse across plans**")
        usage: Dict[str, int] = {}
        for trailer in fleet.trailers:
            for seg in trailer.segments:
                usage[seg.scene_id] = usage.get(seg.scene_id, 0) + 1
        st.bar_chart(usage, horizontal=True)

    html(ui.section("Fleet comparison table", "🧾"))
    table = [
        {
            "Audience": t.audience.replace("_", " ").title(),
            "Status": t.status,
            "Duration (s)": t.duration_seconds,
            "Segments": t.segment_count,
            "Checks": len(t.checks),
            "Pass %": round(t.pass_rate, 1),
            "Warnings": len(t.warnings),
            "Cost $": round(t.estimated_cost, 4),
        }
        for t in fleet.trailers
    ]
    st.dataframe(table, use_container_width=True, hide_index=True)

    html(ui.section("Budget", "💵"))
    html(ui.meter(fleet.total_cost, fleet.budget_limit or 1.0, theme))

    st.write("")
    picker = st.selectbox(
        "Focus audience",
        [t.audience for t in fleet.trailers],
        label_visibility="collapsed",
        key="insight_picker",
    )
    chosen = next((t for t in fleet.trailers if t.audience == picker), fleet.trailers[0])

    d1, d2 = st.columns(2)
    with d1:
        html(ui.section("Scene placement in episode", "🕰️"))
        html(ui.source_strip(_raw_segments(chosen), theme, chosen.episode_duration_ms))
    with d2:
        html(ui.section("Emotional arc", "💗"))
        if chosen.emotional_arc:
            st.line_chart(
                {str(e.get("scene") or f"p{i}"): float(e.get("intensity", 0)) for i, e in enumerate(chosen.emotional_arc)}
            )
        else:
            st.caption("No emotional arc recorded.")

    if fleet.capability:
        st.write("")
        with st.expander("🔍 Capability report", expanded=False):
            st.json(fleet.capability, expanded=False)


# ═══════════════════════════════  VIEW: DOCS  ═══════════════════════════════

def render_docs() -> None:
    html(ui.section("Project documentation", "📖"))
    files = [(icon, name, path) for icon, name, path in vm.DOCS if (ROOT / path).exists()]
    if not files:
        st.info("No documentation files found next to the app.")
        return

    picks = st.radio(
        "Document",
        [name for _i, name, _p in files],
        horizontal=True,
        label_visibility="collapsed",
    )
    chosen = next(p for _i, n, p in files if n == picks)
    st.markdown((ROOT / chosen).read_text(encoding="utf-8", errors="replace"))

    st.divider()
    html(ui.section("CLI reference", "⌨️"))
    st.code(
        """# Full pipeline (group flags come BEFORE the subcommand)
# <episode_package> = your episode dir / manifest (supplied by you, not in repo)
python -m src.cli --config ./config/default_config.yaml --mock \\
    run --package <episode_package> --output ./out/

# Subcommands
python -m src.cli ingest --package <episode_package> --config ./config/default_config.yaml
python -m src.cli plan   --output ./out/
python -m src.cli verify --plans ./out/
python -m src.cli apply-change --event ./change.json --plans ./out/
python -m src.cli replay --session ./replay.jsonl
python -m src.cli report --plans ./out/ --output ./report.md

# Options
--mock          # deterministic fixtures, no API keys
--replay FILE   # replay a recorded session
--budget 5.00   # override the budget
""",
        language="bash",
    )


# ═══════════════════════════════  ROUTER  ═══════════════════════════════

if view == "studio":
    pass  # already rendered above (render_studio ran before pipeline execution)
elif view == "results":
    html(ui.section("Generated trailer plans", "🎞️"))
    render_results()
elif view == "validation":
    render_validation()
elif view == "insights":
    render_insights()
elif view == "docs":
    render_docs()
else:
    go("studio")


# ═══════════════════════════════  DOWNLOADS + FOOTER  ═══════════════════════════════

if fleet:
    st.divider()
    with st.expander("📥  Download artefacts", expanded=False):
        for key, payload in st.session_state["pipeline_results"].items():
            if isinstance(payload, dict):
                blob, ext, mime = json.dumps(payload, indent=2, ensure_ascii=False), "json", "application/json"
            else:
                blob, ext, mime = str(payload), "md", "text/markdown"
            st.download_button(
                f"⬇️  {key}.{ext}",
                data=blob.encode("utf-8"),
                file_name=f"{key}.{ext}",
                mime=mime,
                use_container_width=False,
            )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for key, payload in st.session_state["pipeline_results"].items():
                if isinstance(payload, dict):
                    zf.writestr(f"{key}.json", json.dumps(payload, indent=2, ensure_ascii=False))
                else:
                    zf.writestr(f"{key}.md", str(payload))
            if st.session_state["run_logs"]:
                zf.writestr("pipeline_logs.txt", st.session_state["run_logs"])
        st.download_button(
            "📦  Download complete package (ZIP)",
            data=buffer.getvalue(),
            file_name="trailer_director_results.zip",
            mime="application/zip",
            type="primary",
        )

st.divider()
runs = st.session_state["run_count"]
html(
    ui.empty_state(
        "🎬",
        "Autonomous Trailer Director",
        f"UI v{ui.UI_VERSION} · Streamlit · {runs} run{'s' if runs != 1 else ''} in this session · "
        "Pipeline, rules and verification engine unchanged.",
    )
)
