"""
hub_ui.py — Eclatech Hub Design System
Centralizes all styling, colors, fonts, and reusable UI components.
"""
import base64
import os
import streamlit as st

# ── Design Tokens ─────────────────────────────────────────────────────────────
COLORS = {
    # Backgrounds
    "bg":           "#0a0a0b",
    "surface":      "#111113",
    "elevated":     "#18181b",
    # Borders
    "border":       "rgba(255,255,255,0.07)",
    "border_hover": "rgba(255,255,255,0.12)",
    # Text
    "text":         "#f0ede8",
    "muted":        "#888581",
    "subtle":       "#444240",
    # Brand
    "accent":       "#bed62f",
    "accent_dim":   "rgba(190,214,47,0.12)",
    "accent_glow":  "rgba(190,214,47,0.25)",
    # Semantic
    "green":        "#00d46e",
    "green_dim":    "rgba(0,212,110,0.12)",
    "amber":        "#f5a623",
    "amber_dim":    "rgba(245,166,35,0.10)",
    "blue":         "#4d9fff",
    "blue_dim":     "rgba(77,159,255,0.10)",
    "red":          "#ef4444",
    "red_dim":      "rgba(239,68,68,0.10)",
    # Studio brands
    "fpvr":         "#3b82f6",
    "vrh":          "#8b5cf6",
    "vra":          "#ec4899",
    "njoi":         "#f97316",
}

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Syne:wght@400;500;600;700;800&"
    "family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600&"
    "family=DM+Mono:wght@400;500&display=swap');"
)


# ── Logo (inline SVG recreation of the Eclatech icon + wordmark) ──────────────
def _logo_svg(height=28, color_icon="#bed62f", color_text="#f0ede8"):
    """Inline SVG of the Eclatech icon — 3 horizontal bars with a curve."""
    # Simplified geometric logo mark
    return (
        f'<svg height="{height}" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="2" y="4" width="20" height="5" rx="2.5" fill="{color_icon}"/>'
        f'<rect x="2" y="13" width="16" height="5" rx="2.5" fill="{color_icon}"/>'
        f'<rect x="2" y="22" width="20" height="5" rx="2.5" fill="{color_icon}"/>'
        f'<path d="M22 4 C28 4 28 14 22 14" stroke="{color_icon}" stroke-width="5" fill="none" stroke-linecap="round"/>'
        f'</svg>'
    )


# ── Global CSS ────────────────────────────────────────────────────────────────
@st.cache_data
def global_css():
    """Return the complete Hub CSS theme. Inject via st.markdown(global_css(), unsafe_allow_html=True)."""
    c = COLORS
    return f"""<style>
{FONT_IMPORT}

/* ── Base theme overrides ──────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {{
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: {c['text']} !important;
}}

section[data-testid="stSidebar"] {{ display: none !important; }}
[data-testid="collapsedControl"]  {{ display: none !important; }}

.main .block-container {{
    max-width: 100% !important;
    padding-top: 0.5rem !important;
    padding-bottom: 1rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}}

/* Tighten vertical spacing */
div[data-testid="stVerticalBlock"] > div {{ gap: 0.35rem; }}
[data-testid="stHorizontalBlock"] {{ gap: 0.6rem !important; }}

/* ── Typography ────────────────────────────────────────────── */
h1, h2, h3 {{
    font-family: 'Syne', sans-serif !important;
    letter-spacing: -0.02em !important;
    color: {c['text']} !important;
}}

.stCaptionContainer p {{
    color: {c['muted']} !important;
    font-size: 0.78rem !important;
}}

code, .stCodeBlock {{
    font-family: 'DM Mono', monospace !important;
}}

/* ── Tabs (Vercel-style nav) ───────────────────────────────── */
[data-testid="stTabs"] {{
    border-bottom: 1px solid {c['border']} !important;
}}

[data-testid="stTabs"] button {{
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: {c['muted']} !important;
    padding: 8px 16px !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    transition: color 0.15s, border-color 0.15s !important;
}}

[data-testid="stTabs"] button:hover {{
    color: {c['text']} !important;
}}

[data-testid="stTabs"] button[aria-selected="true"] {{
    color: {c['text']} !important;
    border-bottom: 2px solid {c['accent']} !important;
    background: transparent !important;
}}

/* Remove the default Streamlit tab indicator */
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
    display: none !important;
}}
[data-testid="stTabs"] [data-baseweb="tab-border"] {{
    display: none !important;
}}

/* ── Buttons ───────────────────────────────────────────────── */
.stButton > button {{
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    border-radius: 6px !important;
    border: 1px solid {c['border_hover']} !important;
    background: {c['surface']} !important;
    color: {c['text']} !important;
    transition: background 0.15s, border-color 0.15s !important;
}}

.stButton > button:hover {{
    background: {c['elevated']} !important;
    border-color: {c['accent']}44 !important;
}}

/* Primary / form submit buttons */
.stFormSubmitButton > button {{
    background: {c['accent']} !important;
    color: #0a0a0b !important;
    font-weight: 600 !important;
    border: none !important;
}}

.stFormSubmitButton > button:hover {{
    background: #cce234 !important;
}}

/* ── Inputs ────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
.stSelectbox > div > div {{
    font-family: 'DM Sans', sans-serif !important;
    border-radius: 6px !important;
}}

/* ── Expanders ─────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    border: 1px solid {c['border']} !important;
    border-radius: 8px !important;
    background: {c['surface']} !important;
}}

[data-testid="stExpander"] summary {{
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.85rem !important;
}}

/* ── Metrics ───────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {c['surface']} !important;
    border: 1px solid {c['border']} !important;
    border-radius: 8px !important;
    padding: 12px 16px !important;
}}

[data-testid="stMetric"] label {{
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    color: {c['muted']} !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}}

[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    color: {c['text']} !important;
}}

/* ── Download button ───────────────────────────────────────── */
.stDownloadButton > button {{
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
}}

/* ── Divider ───────────────────────────────────────────────── */
[data-testid="stHorizontalRule"] {{
    border-color: {c['border']} !important;
}}

/* ── Dataframes ────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border: 1px solid {c['border']} !important;
    border-radius: 8px !important;
}}

/* ── Custom component classes ──────────────────────────────── */
.sh {{
    font-family: 'DM Sans', sans-serif;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {c['muted']};
    border-bottom: 1px solid {c['border']};
    padding-bottom: 4px;
    margin: 16px 0 8px;
}}

.hub-card {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 16px;
    margin: 4px 0;
}}

.hub-card-accent {{
    border-left: 3px solid {c['accent']};
}}

.hub-badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 500;
    font-family: 'DM Sans', sans-serif;
    letter-spacing: 0.02em;
}}

.hub-badge-green  {{ background: {c['green_dim']};  color: {c['green']}; }}
.hub-badge-amber  {{ background: {c['amber_dim']};  color: {c['amber']}; }}
.hub-badge-blue   {{ background: {c['blue_dim']};   color: {c['blue']}; }}
.hub-badge-red    {{ background: {c['red_dim']};    color: {c['red']}; }}
.hub-badge-accent {{ background: {c['accent_dim']}; color: {c['accent']}; }}
.hub-badge-gray   {{ background: rgba(255,255,255,0.06); color: {c['muted']}; }}

/* ── Segmented control ─────────────────────────────────────── */
[data-testid="stSegmentedControl"] button {{
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}}

/* ── Progress bars ─────────────────────────────────────────── */
.stProgress > div > div {{
    background-color: {c['accent']} !important;
}}

/* ── Pills ─────────────────────────────────────────────────── */
[data-testid="stPills"] button {{
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.8rem !important;
}}

</style>"""


# ── UI Helper Functions ───────────────────────────────────────────────────────

def logo_header(user_name):
    """Render the branded header bar: logo icon + ECLATECH HUB + user + sign out."""
    c = COLORS
    icon = _logo_svg(height=24)
    st.markdown(
        f"<div style='display:flex;align-items:center;justify-content:space-between;"
        f"margin:0 0 8px;padding:4px 0;border-bottom:1px solid {c['border']}'>"
        f"<div style='display:flex;align-items:center;gap:10px'>"
        f"{icon}"
        f"<span style='font-family:Syne,sans-serif;font-size:1.1rem;font-weight:700;"
        f"letter-spacing:0.06em;color:{c['text']}'>ECLATECH</span>"
        f"<span style='font-family:DM Sans,sans-serif;font-size:0.75rem;font-weight:400;"
        f"color:{c['muted']};margin-left:-4px'>HUB</span>"
        f"</div>"
        f"<span style='font-family:DM Sans,sans-serif;font-size:0.78rem;"
        f"color:{c['muted']}'>{user_name}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


def login_page():
    """Render the branded login page."""
    c = COLORS
    icon = _logo_svg(height=48, color_icon=c["accent"])
    st.markdown(
        f"<div style='text-align:center;margin-top:140px'>"
        f"<div style='margin-bottom:16px'>{icon}</div>"
        f"<div style='font-family:Syne,sans-serif;font-size:2rem;font-weight:800;"
        f"letter-spacing:0.04em;color:{c['text']}'>ECLATECH</div>"
        f"<div style='font-family:DM Sans,sans-serif;font-size:0.9rem;"
        f"color:{c['muted']};margin:8px 0 40px'>Hub</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def denied_page(email):
    """Render the access denied page."""
    c = COLORS
    st.markdown(
        f"<div style='text-align:center;margin-top:140px'>"
        f"<div style='font-family:Syne,sans-serif;font-size:1.4rem;font-weight:700;"
        f"color:{c['red']}'>Access Denied</div>"
        f"<p style='font-family:DM Sans,sans-serif;color:{c['muted']};"
        f"margin:16px 0'>{email} is not authorized.</p>"
        f"<p style='font-family:DM Sans,sans-serif;color:{c['subtle']};"
        f"font-size:0.85rem'>Contact Drew for access.</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


def section(title):
    """Styled section header."""
    st.markdown(f"<div class='sh'>{title}</div>", unsafe_allow_html=True)


def card(html, accent=None):
    """Bordered card container."""
    cls = "hub-card hub-card-accent" if accent else "hub-card"
    border_style = f"border-left-color:{accent};" if accent else ""
    st.markdown(f"<div class='{cls}' style='{border_style}'>{html}</div>",
                unsafe_allow_html=True)


def badge(text, variant="gray"):
    """Inline badge/pill. Variants: green, amber, blue, red, accent, gray."""
    return f"<span class='hub-badge hub-badge-{variant}'>{text}</span>"


def status_dot(color):
    """Small colored dot."""
    return f"<span style='display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:6px'></span>"


def freshness_bar(ts_key, bust_keys, label=""):
    """Show 'Updated Xm ago' text + Refresh button. Call at top of data views.
    ts_key: session_state key holding the cache timestamp.
    bust_keys: list of session_state keys to pop on refresh.
    """
    import time as _time
    _ts = st.session_state.get(ts_key, 0)
    if _ts:
        _ago = int(_time.time() - _ts)
        if _ago < 60:
            _age_str = "just now"
        elif _ago < 3600:
            _age_str = f"{_ago // 60}m ago"
        else:
            _age_str = f"{_ago // 3600}h ago"
    else:
        _age_str = "not loaded"
    _c1, _c2 = st.columns([4, 1])
    with _c1:
        st.markdown(
            f"<span style='font-size:0.72rem;color:{COLORS['muted']}'>"
            f"Updated {_age_str}</span>",
            unsafe_allow_html=True,
        )
    with _c2:
        if st.button("Refresh", key=f"refresh_{ts_key}", use_container_width=True):
            for k in bust_keys:
                st.session_state.pop(k, None)
            st.rerun()
