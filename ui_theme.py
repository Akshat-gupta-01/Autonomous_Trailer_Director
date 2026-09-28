"""UI design system: theme tokens, CSS injection and reusable HTML widgets.

Purely presentational. No pipeline logic lives here.
"""

from __future__ import annotations

import html
from typing import Any, Dict, Optional, Sequence

# ──────────────────────────────  THEME TOKENS  ──────────────────────────────

THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        "bg": "#0a0a0f",
        "bg2": "#12121a",
        "card": "rgba(255,255,255,0.04)",
        "card2": "rgba(255,255,255,0.025)",
        "border": "rgba(255,215,0,0.15)",
        "border2": "rgba(255,215,0,0.25)",
        "text": "#f5f0e8",
        "muted": "#b8a890",
        "accent": "#ffd700",
        "accent2": "#1e90ff",
        "ok": "#32cd32",
        "warn": "#ffd700",
        "err": "#ff4757",
        "info": "#1e90ff",
        "shadow": "0 18px 50px -20px rgba(0,0,0,0.9)",
        "track": "rgba(255,215,0,0.1)",
    },
    "light": {
        "bg": "#fefcf5",
        "bg2": "#ffffff",
        "card": "#ffffff",
        "card2": "#fefef8",
        "border": "rgba(255,215,0,0.2)",
        "border2": "rgba(30,144,255,0.25)",
        "text": "#1a1a15",
        "muted": "#8a7a60",
        "accent": "#b8860b",
        "accent2": "#1e90ff",
        "ok": "#2e8b57",
        "warn": "#daa520",
        "err": "#dc143c",
        "info": "#1e90ff",
        "shadow": "0 16px 40px -22px rgba(0,0,0,0.3)",
        "track": "rgba(30,144,255,0.1)",
    },
}

STATUS_COLORS = {
    "PASS": "ok",
    "PASS_WITH_WARNINGS": "warn",
    "WARN": "warn",
    "FAIL": "err",
    "REJECTED": "err",
    "UNKNOWN": "muted",
    "PENDING": "muted",
}

VERDICT_COLORS = {"PASS": "ok", "WARN": "warn", "FAIL": "err"}

UI_VERSION = "2.0"


def t(theme: str, key: str) -> str:
    """Resolve a design token for a theme, falling back to dark."""
    return THEMES.get(theme, THEMES["dark"]).get(key, "#fff")


def esc(value: Any) -> str:
    """HTML-escape any value."""
    return html.escape("" if value is None else str(value), quote=True)


# ──────────────────────────────  CSS BUILDER  ──────────────────────────────

_CSS_TEMPLATE = """
<style>
/* ===== tokens ===== */
:root{
  --bg:__BG__; --bg2:__BG2__;
  --card:__CARD__; --card2:__CARD2__;
  --border:__BORDER__; --border2:__BORDER2__;
  --text:__TEXT__; --muted:__MUTED__;
  --accent:__ACCENT__; --accent2:__ACCENT2__;
  --ok:__OK__; --warn:__WARN__; --err:__ERR__; --info:__INFO__;
  --shadow:__SHADOW__; --track:__TRACK__;
  --radius:16px; --radius-sm:10px;
}
html, body, [class*="css"]{ font-feature-settings:"cv02","cv03","cv04","cv11"; }
.stApp{
  background:
    radial-gradient(1100px 620px at 12% -8%, color-mix(in srgb, var(--accent) 26%, transparent), transparent 62%),
    radial-gradient(900px 520px at 92% 4%, color-mix(in srgb, var(--accent2) 20%, transparent), transparent 60%),
    linear-gradient(180deg, var(--bg) 0%, var(--bg2) 46%, var(--bg) 100%);
  background-attachment: fixed;
  color: var(--text);
}
.block-container{ padding-top:1.6rem; padding-bottom:4rem; max-width:1500px; }
[data-testid="stHeader"]{ background:transparent; }
hr, [data-testid="stDivider"]{ border-color:var(--border); }

/* ===== typography ===== */
h1,h2,h3,h4,h5{ color:var(--text) !important; letter-spacing:-0.02em; }
p, label, span, li, td, th{ color:var(--text); }
[data-testid="stCaptionContainer"], small, .stCaption{ color:var(--muted) !important; }
code, pre{ font-family:"JetBrains Mono","Cascadia Code",ui-monospace,Menlo,Consolas,monospace !important; }
[data-testid="stCodeBlock"]{
  background:var(--card2) !important; border:1px solid var(--border); border-radius:var(--radius-sm);
}
[data-testid="stCodeBlock"] code{ font-size:.82rem !important; line-height:1.55 !important; }

/* ===== sidebar ===== */
[data-testid="stSidebar"]{
  background:color-mix(in srgb, var(--bg2) 72%, transparent) !important;
  border-right:1px solid var(--border); backdrop-filter:blur(18px);
}
[data-testid="stSidebar"] .block-container{ padding-top:1.1rem; }
[data-testid="stSidebarCollapseButton"]{ color:var(--muted); }
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{ font-size:1rem; }
[data-testid="stExpander"] details, details[data-testid="stExpander"]{
  background:var(--card2); border:1px solid var(--border); border-radius:var(--radius-sm);
}
summary{ color:var(--text) !important; font-weight:600; }
summary:hover{ color:var(--accent2) !important; }

/* ===== widgets ===== */
.stButton > button, .stDownloadButton > button{
  border-radius:999px; border:1px solid var(--border2); background:var(--card2);
  color:var(--text); font-weight:600; padding:.42rem 1.05rem; transition:all .18s ease;
  box-shadow:none;
}
/* Narrow columns must not wrap button labels one character per line. */
.stButton > button p, .stDownloadButton > button p{
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:.86rem;
}
[data-testid="stButton"] > button{ min-width:0; padding-inline:.5rem; }
.stButton, .stDownloadButton{ min-width:0; }
.stButton > button:hover, .stDownloadButton > button:hover{
  transform:translateY(-1px); border-color:var(--accent);
  color:var(--accent2); box-shadow:0 8px 24px -14px var(--accent);
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"]{
  background:linear-gradient(100deg, var(--accent), var(--accent2));
  border:none; color:#fff; box-shadow:0 14px 34px -18px var(--accent);
}
.stButton > button[kind="primary"]:hover{ filter:brightness(1.08); color:#fff; }
.stButton > button:disabled, .stDownloadButton > button:disabled{
  opacity:.42; transform:none; box-shadow:none; color:var(--muted);
}
[data-baseweb="select"] > div, [data-baseweb="input"] > div{
  background:var(--card2) !important; border-color:var(--border) !important;
  border-radius:var(--radius-sm) !important; color:var(--text) !important;
}
input, textarea, [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input{
  color:var(--text) !important; font-family:inherit;
}
textarea{ font-family:"JetBrains Mono",ui-monospace,Consolas,monospace !important; font-size:.78rem !important; }
[data-testid="stFileUploaderDropzone"]{
  background:var(--card2); border:1.5px dashed var(--border2); border-radius:var(--radius);
  padding:.85rem .6rem; transition:all .18s ease;
}
[data-testid="stFileUploaderDropzone"]:hover{ border-color:var(--accent); background:color-mix(in srgb,var(--accent) 9%, var(--card2)); }
[data-testid="stFileUploaderDropzone"] small, [data-testid="stFileUploaderDropzoneInstructions"] span{ color:var(--muted) !important; }
[data-testid="stFileUploaderFile"]{
  background:color-mix(in srgb,var(--ok) 12%, var(--card2)); border:1px solid var(--border2);
  border-radius:var(--radius-sm);
}
/* radio / segmented */
[data-testid="stRadio"] [role="radiogroup"]{
  background:var(--card2); border:1px solid var(--border); border-radius:999px; padding:3px; gap:2px;
}
[data-testid="stRadio"] [role="radiogroup"] > label{
  border-radius:999px !important; padding:.28rem .5rem !important; transition:all .16s ease;
}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked){
  background:linear-gradient(100deg,var(--accent),var(--accent2));
}
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) p{ color:#fff !important; font-weight:650; }
[data-testid="stSlider"] [role="slider"]{ background:var(--accent) !important; }
[data-testid="stSlider"] [data-testid="stTickBarMin"], [data-testid="stSlider"] [data-testid="stTickBarMax"]{ color:var(--muted); }

/* progress + status */
[data-testid="stProgress"] > div > div > div{
  background:linear-gradient(90deg,var(--accent),var(--accent2)) !important; border-radius:999px;
}
[data-testid="stStatusWidget"]{ background:var(--card2); border:1px solid var(--border); border-radius:var(--radius); }
[data-testid="stAlert"]{ border-radius:var(--radius); border:1px solid var(--border); background:var(--card2); }

/* dataframe */
[data-testid="stDataFrame"]{ border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
[data-testid="stDataFrame"] *{ font-size:.8rem !important; }

/* ===== custom components ===== */
.atd-hero{
  position:relative; overflow:hidden; border-radius:22px; padding:1.5rem 1.7rem;
  border:1px solid var(--border2);
  background:linear-gradient(115deg,
     color-mix(in srgb,var(--accent) 30%, var(--card2)) 0%,
     color-mix(in srgb,var(--accent2) 20%, var(--card2)) 55%,
     var(--card2) 100%);
  box-shadow:var(--shadow); margin-bottom:1.15rem;
}
.atd-hero::after{
  content:""; position:absolute; inset:0;
  background:radial-gradient(520px 220px at 88% -30%, color-mix(in srgb,#fff 22%, transparent), transparent 70%);
  pointer-events:none;
}
.atd-hero-eyebrow{
  font-size:.68rem; font-weight:750; letter-spacing:.20em; text-transform:uppercase;
  color:var(--accent2); margin-bottom:.35rem;
}
.atd-hero h1{ font-size:2.35rem; font-weight:800; line-height:1.1; margin:0 0 .35rem; }
.atd-hero p{ margin:0; color:var(--muted); font-size:.93rem; max-width:62ch; }
.atd-chips{ display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.85rem; }

.atd-chip{
  display:inline-flex; align-items:center; gap:.32rem; font-size:.7rem; font-weight:600;
  padding:.26rem .6rem; border-radius:999px; border:1px solid var(--border2);
  background:var(--card); color:var(--muted); backdrop-filter:blur(6px);
}
.atd-chip b{ color:var(--text); font-weight:700; }

.atd-card{
  background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
  padding:1rem 1.05rem; box-shadow:var(--shadow); position:relative; overflow:hidden;
  transition:transform .18s ease, border-color .18s ease;
}
.atd-card:hover{ transform:translateY(-2px); border-color:var(--border2); }
.atd-card-accent{ position:absolute; left:0; top:0; bottom:0; width:3px;
  background:linear-gradient(180deg,var(--accent),var(--accent2)); }

.atd-section{ display:flex; align-items:center; gap:.6rem; margin:1.5rem 0 .75rem; }
.atd-section h3{ margin:0; font-size:1.12rem; font-weight:720; }
.atd-section .atd-rule{ flex:1; height:1px; background:linear-gradient(90deg,var(--border2),transparent); }

.atd-kpi{ background:var(--card); border:1px solid var(--border); border-radius:var(--radius);
  padding:.85rem .95rem; box-shadow:var(--shadow); }
.atd-kpi .lbl{ font-size:.66rem; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:700; }
.atd-kpi .val{ font-size:1.65rem; font-weight:800; line-height:1.2; margin-top:.15rem; color:var(--text); }
.atd-kpi .sub{ font-size:.72rem; color:var(--muted); margin-top:.1rem; }

.atd-badge{
  display:inline-flex; align-items:center; gap:.3rem; font-size:.7rem; font-weight:750;
  padding:.24rem .6rem; border-radius:999px; letter-spacing:.03em; white-space:nowrap;
  border:1px solid currentColor;
}
.atd-dot{ width:7px; height:7px; border-radius:50%; background:currentColor; box-shadow:0 0 8px currentColor; }

.atd-tl{ margin-top:.6rem; }
.atd-tl-track{ display:flex; gap:3px; height:40px; border-radius:9px; overflow:hidden;
  border:1px solid var(--border); background:var(--track); }
.atd-tl-seg{ display:flex; flex-direction:column; justify-content:center; align-items:center;
  color:#fff; font-size:.66rem; font-weight:700; overflow:hidden; white-space:nowrap;
  transition:filter .18s ease; }
.atd-tl-seg:hover{ filter:brightness(1.18); }
.atd-tl-meta{ display:flex; justify-content:space-between; font-size:.7rem; color:var(--muted); margin-top:.35rem; }

.atd-stage{ display:flex; align-items:center; gap:.7rem; padding:.42rem .1rem; }
.atd-stage .bubble{
  width:26px; height:26px; min-width:26px; border-radius:50%; display:grid; place-items:center;
  font-size:.7rem; font-weight:800; border:1px solid var(--border2); background:var(--card2); color:var(--muted);
}
.atd-stage.done .bubble{ background:linear-gradient(120deg,var(--accent),var(--accent2)); color:#fff; border-color:transparent; }
.atd-stage.active .bubble{ border-color:var(--accent2); color:var(--accent2); box-shadow:0 0 0 4px color-mix(in srgb,var(--accent2) 18%, transparent); }
.atd-stage .nm{ font-size:.83rem; font-weight:600; }
.atd-stage .ds{ font-size:.7rem; color:var(--muted); }
.atd-stage::after{ content:""; flex:1; height:1px; background:var(--border); }
.atd-stage:last-child::after{ display:none; }

.atd-empty{ text-align:center; padding:2.6rem 1rem; border:1.5px dashed var(--border2);
  border-radius:var(--radius); background:var(--card2); }
.atd-empty .ico{ font-size:2.4rem; }
.atd-empty h4{ margin:.5rem 0 .25rem; font-size:1.05rem; }
.atd-empty p{ color:var(--muted); font-size:.85rem; margin:0; }

.atd-file{ display:flex; align-items:center; gap:.5rem; font-size:.75rem; color:var(--muted);
  padding:.3rem .5rem; border:1px solid var(--border); border-radius:999px; background:var(--card2); }

.atd-donut{ width:132px; height:132px; border-radius:50%; display:grid; place-items:center;
  background:conic-gradient(__DONUT__); }
.atd-donut-in{ width:96px; height:96px; border-radius:50%; background:var(--card2);
  display:grid; place-items:center; text-align:center; border:1px solid var(--border); }
.atd-donut-in b{ font-size:1.3rem; font-weight:800; }
.atd-donut-in span{ font-size:.62rem; color:var(--muted); letter-spacing:.1em; text-transform:uppercase; }

.atd-legend{ display:flex; flex-direction:column; gap:.3rem; }
.atd-legend div{ font-size:.76rem; color:var(--muted); display:flex; align-items:center; gap:.45rem; }
.atd-legend i{ width:9px; height:9px; border-radius:3px; display:inline-block; }

.atd-json{ font-size:.74rem; line-height:1.5; }
.atd-foot{ text-align:center; color:var(--muted); font-size:.72rem; margin-top:2rem; }

/* scrollbars */
::-webkit-scrollbar{ width:9px; height:9px; }
::-webkit-scrollbar-track{ background:transparent; }
::-webkit-scrollbar-thumb{ background:var(--border2); border-radius:99px; }
::-webkit-scrollbar-thumb:hover{ background:var(--accent); }
</style>
"""


def build_css(theme: str, donut: str = "") -> str:
    """Return the full stylesheet for a theme."""
    css = _CSS_TEMPLATE
    for key, token in (
        ("BG", "bg"), ("BG2", "bg2"), ("CARD", "card"), ("CARD2", "card2"),
        ("BORDER", "border"), ("BORDER2", "border2"), ("TEXT", "text"), ("MUTED", "muted"),
        ("ACCENT", "accent"), ("ACCENT2", "accent2"), ("OK", "ok"), ("WARN", "warn"),
        ("ERR", "err"), ("INFO", "info"), ("SHADOW", "shadow"), ("TRACK", "track"),
    ):
        css = css.replace(f"__{key}__", t(theme, token))
    return css.replace("__DONUT__", donut or t(theme, "track"))


# ──────────────────────────────  HTML WIDGETS  ──────────────────────────────

def hero(eyebrow: str, title: str, subtitle: str, chips: Optional[Sequence[str]] = None) -> str:
    chip_html = "".join(f'<span class="atd-chip">{c}</span>' for c in (chips or []))
    return f"""
<div class="atd-hero">
  <div class="atd-hero-eyebrow">{esc(eyebrow)}</div>
  <h1>{esc(title)}</h1>
  <p>{esc(subtitle)}</p>
  <div class="atd-chips">{chip_html}</div>
</div>"""


def section(title: str, icon: str = "", right: str = "") -> str:
    return f"""
<div class="atd-section">
  <h3>{icon} {esc(title)}</h3>
  <div class="atd-rule"></div>
  {right}
</div>"""


def kpi(label: str, value: str, sub: str = "", tone: str = "") -> str:
    color = f"color:{tone};" if tone else ""
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    return f"""<div class="atd-kpi">
  <div class="lbl">{esc(label)}</div>
  <div class="val" style="{color}">{esc(value)}</div>
  {sub_html}
</div>"""


def kpi_row(items: Sequence[Dict[str, str]]) -> str:
    return f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem">{"".join(items)}</div>'


def badge(label: str, tone: str, theme: str, dot: bool = True) -> str:
    color = t(theme, tone if tone in THEMES["dark"] else "muted")
    dot_html = '<span class="atd-dot"></span>' if dot else ""
    return f'<span class="atd-badge" style="color:{color}">{dot_html}{esc(label)}</span>'


def status_badge(status: str, theme: str) -> str:
    tone = STATUS_COLORS.get(str(status).upper(), "muted")
    return badge(str(status).replace("_", " "), tone, theme)


def card(inner: str, accent: bool = False) -> str:
    bar = '<div class="atd-card-accent"></div>' if accent else ""
    return f'<div class="atd-card">{bar}{inner}</div>'


def card_kv(pairs: Sequence[Sequence[Any]], theme: str) -> str:
    rows = []
    for key, value in pairs:
        rows.append(
            f'<div style="display:flex;gap:.7rem;align-items:flex-start;padding:.3rem 0;'
            f'border-bottom:1px dashed var(--border)">'
            f'<div style="min-width:118px;font-size:.72rem;color:var(--muted);'
            f'font-weight:650;text-transform:uppercase;letter-spacing:.05em">{esc(key)}</div>'
            f'<div style="font-size:.87rem;flex:1">{esc(value)}</div></div>'
        )
    return card("".join(rows), accent=True)


def empty_state(icon: str, title: str, body: str) -> str:
    return f"""<div class="atd-empty">
  <div class="ico">{icon}</div>
  <h4>{esc(title)}</h4>
  <p>{esc(body)}</p>
</div>"""


def file_chips(files: Dict[str, Any], theme: str, labels: Dict[str, str]) -> str:
    chips = []
    for key, label in labels.items():
        obj = files.get(key)
        if obj is None:
            continue
        name = getattr(obj, "name", None) or (obj.name if hasattr(obj, "name") else str(obj))
        size = getattr(obj, "size", None)
        suffix = f" · {size/1024:.0f} KB" if isinstance(size, (int, float)) and size else ""
        chips.append(f'<span class="atd-file">📎 {esc(label)}: <b>{esc(name)}</b>{esc(suffix)}</span>')
    return f'<div style="display:flex;flex-wrap:wrap;gap:.4rem">{"".join(chips)}</div>' if chips else ""


def timeline(segments: Sequence[Dict[str, Any]], theme: str, arc: Optional[Sequence[str]] = None) -> str:
    """Render a proportional EDL timeline with arc colouring."""
    segs = [s for s in segments if isinstance(s, dict)]
    if not segs:
        return ""
    durations = [float(s.get("source", {}).get("duration_ms") or 0) for s in segs]
    total = sum(durations) or 1.0
    palette = ["accent", "accent2", "info", "ok", "warn", "err"]
    blocks = []
    for i, (seg, dur) in enumerate(zip(segs, durations)):
        pct = max(dur / total * 100, 4)
        tone = palette[i % len(palette)]
        order = seg.get("sequence_order", i)
        title = esc(seg.get("source", {}).get("scene_id", f"seg{order}"))
        blocks.append(
            f'<div class="atd-tl-seg" style="width:{pct:.2f}%;'
            f'background:linear-gradient(140deg,{t(theme, tone)},{t(theme, "accent2")});" '
            f'title="{title} · {dur/1000:.1f}s">{order}</div>'
        )
    arc_html = ""
    if arc:
        arc_html = f'<div class="atd-tl-meta"><span>{" → ".join(esc(a) for a in arc)}</span><span>{len(segs)} segments</span></div>'
    return f"""<div class="atd-tl">
  <div class="atd-tl-track">{"".join(blocks)}</div>
  {arc_html}
</div>"""


def source_strip(segments: Sequence[Dict[str, Any]], theme: str, episode_ms: float) -> str:
    """Show where each clip sits inside the source episode."""
    segs = [s for s in segments if isinstance(s, dict)]
    if not segs or not episode_ms:
        return ""
    rows = []
    for seg in segs:
        src = seg.get("source", {})
        start = float(src.get("source_in_ms") or 0)
        end = float(src.get("source_out_ms") or 0)
        left = min(start / episode_ms * 100, 99)
        width = max(min((end - start) / episode_ms * 100, 99 - left), 1.2)
        rows.append(
            f'<div style="position:relative;height:9px;border-radius:99px;background:var(--track);margin:.28rem 0">'
            f'<div style="position:absolute;left:{left:.2f}%;width:{width:.2f}%;top:0;bottom:0;'
            f'border-radius:99px;background:linear-gradient(90deg,{t(theme,"accent")},{t(theme,"accent2")})"></div>'
            f'</div>'
            f'<div style="font-size:.68rem;color:var(--muted);margin-bottom:.15rem">'
            f'#{esc(seg.get("sequence_order","?"))} {esc(src.get("scene_id",""))} '
            f'· {esc(src.get("source_in",""))} → {esc(src.get("source_out",""))}</div>'
        )
    return "".join(rows)


def donut(pairs: Sequence[Sequence[Any]], theme: str, center_value: str, center_label: str) -> str:
    """Ring chart built from pure CSS conic-gradient."""
    pairs = [(str(k), int(v)) for k, v in pairs if int(v) > 0]
    total = sum(v for _, v in pairs) or 1
    stops, cursor = [], 0.0
    for key, value in pairs:
        start = cursor
        cursor += value / total * 100
        stops.append(f"{t(theme, VERDICT_COLORS.get(key, 'muted'))} {start:.2f}% {cursor:.2f}%")
    legend = "".join(
        f'<div><i style="background:{t(theme, VERDICT_COLORS.get(k, "muted"))}"></i>{esc(k)} · {v}</div>'
        for k, v in pairs
    )
    return f"""
<div style="display:flex;align-items:center;gap:1.1rem;flex-wrap:wrap">
  <div class="atd-donut" style="background:conic-gradient({', '.join(stops) or t(theme,'track')})">
    <div class="atd-donut-in"><b>{esc(center_value)}</b><span>{esc(center_label)}</span></div>
  </div>
  <div class="atd-legend">{legend}</div>
</div>"""


def stages(items: Sequence[Sequence[str]], active: int = -1, completed: int = -1) -> str:
    """Vertical pipeline stage tracker."""
    out = []
    for i, (name, desc) in enumerate(items):
        if i <= completed:
            cls, bubble = "done", "✓"
        elif i == active:
            cls, bubble = "active", str(i + 1)
        else:
            cls, bubble = "", str(i + 1)
        out.append(
            f'<div class="atd-stage {cls}"><div class="bubble">{bubble}</div>'
            f'<div><div class="nm">{esc(name)}</div><div class="ds">{esc(desc)}</div></div></div>'
        )
    return f'<div class="atd-card">{"".join(out)}</div>'


def meter(used: float, limit: float, theme: str) -> str:
    ratio = 0.0 if not limit else max(0.0, min(used / limit, 1.0))
    tone = "err" if ratio > 0.9 else ("warn" if ratio > 0.7 else "ok")
    return f"""
<div style="font-size:.72rem;color:var(--muted);display:flex;justify-content:space-between">
  <span>Budget used</span><span>${used:.4f} / ${limit:.2f}</span></div>
<div style="height:9px;border-radius:99px;background:var(--track);margin-top:.3rem;overflow:hidden">
  <div style="height:100%;width:{ratio*100:.1f}%;border-radius:99px;
       background:linear-gradient(90deg,{t(theme, tone)},{t(theme,'accent2')})"></div>
</div>"""
