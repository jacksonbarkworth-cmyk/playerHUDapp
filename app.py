import streamlit as st
import math
import json
import requests

st.set_page_config(page_title="Player HUD", layout="wide")

# ---------- STATE ----------
if "section" not in st.session_state:
    st.session_state.section = "XP Breakdown"

# ---------- XP BREAKDOWN DEFAULTS (SOURCE OF TRUTH) ----------
DEFAULT_XP_VALUES = {
    "Admin Work": 4.0,
    "Design Work": 0.0,
    "Jiu Jitsu Training": 0.0,
    "Gym Workout": 0.0,
    "Italian Studying": 0.0,
    "Italian Passive listening": 0.0,
    "Chess - Rated Matches": 0.0,
    "Chess - Study/ Analysis": 0.0,
    "Reading": 0.0,
    "New Skill Learning": 0.0,
    "Personal Challenge Quest": 0.0,
    "Recovery": 0.0,
    "Creative Output": 0.0,
    "General Life Task": 0.0,
    "Quest 1": 0.0,
    "Quest 2": 0.0,
    "Quest 3": 1.0,
    "Chess Streak": 0.0,
    "Italian Streak": 0.0,
    "Gym Streak": 0.0,
    "Jiu Jitsu Streak": 0.0,
    "Eating Healthy": 1.0,
    "Meet Hydration target": 1.0,
}

# ---------- XP WALL DEBT DEFAULTS (SOURCE OF TRUTH) ----------
DEFAULT_DEBT_VALUES = {
    "Skip Training": 0.0,
    "Junk Eating": 0.0,
    "Drug Use": 0.0,
    "Blackout Drunk": 0.0,
    "Reckless Driving": 0.0,
    "Start Fight": 0.0,
    "Doomscrolling": 0.0,
    "Miss Work": 0.0,
    "Impulsive Spend": 0.0,
    "Malicious Deceit": 0.0,
    "Break Oath": 0.0,
    "All Nighter": 0.0,
    "Avoid Duty": 0.0,
    "Ignore Injury": 0.0,
    "Miss Hydration": 0.0,
    "Sleep Collapse": 0.0,
    "Ghost Obligation": 0.0,
    "Ego Decisions": 0.0,
    "No Logging": 0.0,
    "Message Pile": 0.0,
    "Quest Miss": 0.0,
}

# ---------- HELPERS ----------
def coerce_and_align(loaded: dict, defaults: dict) -> dict:
    """
    Keep only the default keys, fill missing keys from defaults,
    and coerce values to float safely.
    """
    out = {}
    for k, dv in defaults.items():
        try:
            out[k] = float(loaded.get(k, dv))
        except Exception:
            out[k] = float(dv)
    return out

# ---------- CLOUD SAVE (SUPABASE) ----------
CLOUD_ENABLED = (
    "SUPABASE_URL" in st.secrets
    and "SUPABASE_SERVICE_ROLE_KEY" in st.secrets
    and "SAVE_KEY" in st.secrets
)

if CLOUD_ENABLED:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].rstrip("/")
    SUPABASE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    SAVE_KEY = st.secrets["SAVE_KEY"]

    _SB_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    def cloud_load_state():
        url = f"{SUPABASE_URL}/rest/v1/player_state"
        params = {"save_key": f"eq.{SAVE_KEY}", "select": "xp_values,debt_values"}
        r = requests.get(url, headers=_SB_HEADERS, params=params, timeout=15)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase load failed ({r.status_code}): {r.text}")
        rows = r.json()
        if not rows:
            return None
        return rows[0].get("xp_values", {}), rows[0].get("debt_values", {})

    def cloud_save_state(xp_values: dict, debt_values: dict):
        url = f"{SUPABASE_URL}/rest/v1/player_state"
        payload = {"save_key": SAVE_KEY, "xp_values": xp_values, "debt_values": debt_values}
        headers = {**_SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase save failed ({r.status_code}): {r.text}")
else:
    def cloud_load_state():
        return None

    def cloud_save_state(xp_values: dict, debt_values: dict):
        return None

# ---------- CLOUD INIT (XP + DEBT) ----------
# IMPORTANT: If cloud is down/misconfigured, app should still run with defaults.
if "xp_values" not in st.session_state or "debt_values" not in st.session_state:
    try:
        loaded = cloud_load_state()
    except Exception as e:
        st.warning(f"Cloud sync unavailable. Using local defaults for this session.\n\nDetails: {e}")
        loaded = None

    if loaded is None:
        st.session_state.xp_values = DEFAULT_XP_VALUES.copy()
        st.session_state.debt_values = DEFAULT_DEBT_VALUES.copy()
        # Try seeding cloud, but don't crash if it fails
        try:
            cloud_save_state(st.session_state.xp_values, st.session_state.debt_values)
        except Exception as e:
            st.warning(f"Could not seed cloud save.\n\nDetails: {e}")
    else:
        xp_loaded, debt_loaded = loaded
        st.session_state.xp_values = coerce_and_align(xp_loaded, DEFAULT_XP_VALUES)
        st.session_state.debt_values = coerce_and_align(debt_loaded, DEFAULT_DEBT_VALUES)

# ---------- BACKGROUND RULES: LEVEL + TITLE SYSTEM ----------
MAX_LEVEL = 100

TITLE_RANGES = [
    ("Novice", 1, 5),
    ("Trainee", 6, 10),
    ("Adept", 11, 15),
    ("Knight", 16, 20),
    ("Champion", 21, 25),
    ("Elite", 26, 30),
    ("Legend", 31, 35),
    ("Mythic", 36, 40),
    ("Master", 41, 45),
    ("Grandmaster", 46, 50),
    ("Ascendant", 51, 55),
    ("Exemplar", 56, 60),
    ("Paragon", 61, 65),
    ("Titan", 66, 70),
    ("Sovereign", 71, 75),
    ("Immortal-Seed", 76, 80),
    ("Immortal", 81, 85),
    ("Eternal-Seed", 86, 90),
    ("Eternal", 91, 95),
    ("World-Class", 96, 100),
]

def level_requirement(level: int) -> float:
    return float(level * 10)

def title_for_level(level: int) -> str:
    for title, lo, hi in TITLE_RANGES:
        if lo <= level <= hi:
            return title
    return "Unranked"

def title_next_threshold(level: int) -> int:
    for _title, lo, hi in TITLE_RANGES:
        if lo <= level <= hi:
            next_level = hi + 1
            return next_level if next_level <= TITLE_RANGES[-1][2] else hi
    return level

def compute_level(total_xp: float, max_level: int = MAX_LEVEL) -> tuple[int, float, float]:
    total_xp_int = max(0, int(math.floor(total_xp)))

    level = 1
    remaining = float(total_xp_int)

    while level < max_level:
        req = level_requirement(level)
        if remaining >= req:
            remaining -= req
            level += 1
        else:
            break

    req = level_requirement(level)
    xp_in_level = remaining
    return level, xp_in_level, req

# ---------- GLOBAL STYLES ----------
st.markdown(
    """
    <style>
    html, body { height: 100%; }
    [data-testid="stApp"]{
        background:
            linear-gradient(180deg, #020412 0%, #0a0f28 60%, #121845 100%),
            radial-gradient(circle at 80% 50%, rgba(0,255,255,0.18), transparent 55%),
            repeating-linear-gradient(90deg, rgba(0,255,255,0.03) 0px, rgba(0,255,255,0.03) 1px, transparent 1px, transparent 40px),
            repeating-linear-gradient(180deg, rgba(0,255,255,0.03) 0px, rgba(0,255,255,0.03) 1px, transparent 1px, transparent 40px);
        background-blend-mode: normal, screen, normal, normal;
        min-height: 100vh;
        color: white;
        font-family: sans-serif;
    }
    header, [data-testid="stHeader"], [data-testid="stToolbar"] { background: transparent !important; }

    section.main > div.block-container{
        max-width: 1200px !important;
        padding-top: 38px !important;
        padding-bottom: 38px !important;
        padding-left: 18px !important;
        padding-right: 18px !important;
        margin: 0 auto !important;
    }

    .hud-title{
        font-weight: 900;
        font-size: clamp(28px, 4vw, 46px);
        color: #fff;
        text-shadow: 0 0 20px rgba(0,220,255,1), 0 0 40px rgba(0,180,255,0.7);
        margin: 10px 0 16px 0;
        text-align: left;
    }

    .hud-box, .progress-box{
        width: 100%;
        max-width: 420px;
        padding: 16px 20px;
        border-radius: 12px;
        background: rgba(0,3,20,0.55);
        border: 2px solid rgba(0,220,255,0.5);
        box-shadow: 0 0 26px rgba(0,220,255,0.7), inset 0 0 16px rgba(0,220,255,0.25);
        line-height: 1.7;
        font-size: clamp(14px, 1.2vw, 18px);
        margin-bottom: 14px;
    }

    .glow-bar{
        width: 100%;
        height: 22px;
        border-radius: 999px;
        background: rgba(0,0,0,0.45);
        border: 1px solid rgba(0,220,255,0.35);
        box-shadow: 0 0 14px rgba(0,220,255,0.45);
        overflow: hidden;
        position: relative;
        margin-top: 10px;
    }
    .glow-bar-fill{
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, rgba(0,180,255,0.85), rgba(0,255,255,0.75));
        box-shadow: 0 0 18px rgba(0,255,255,1), 0 0 34px rgba(0,180,255,0.9);
        transition: width 0.25s ease-out;
    }
    .glow-bar-fill-red{
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, rgba(255,60,60,0.90), rgba(255,120,80,0.75));
        box-shadow: 0 0 18px rgba(255,60,60,1), 0 0 34px rgba(255,120,80,0.7);
        transition: width 0.25s ease-out;
    }
    .glow-bar-text{
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 900;
        font-size: 13px;
        color: rgba(255,255,255,0.95);
        text-shadow: 0 0 10px rgba(0,220,255,0.7);
        pointer-events: none;
    }
    .glow-bar-text-red{
        text-shadow: 0 0 10px rgba(255,80,80,0.65);
    }

    .bar-label{
        margin-top: 10px;
        font-weight: 900;
        font-size: 13px;
        letter-spacing: 0.3px;
        opacity: 0.92;
        text-shadow: 0 0 10px rgba(0,220,255,0.45);
    }

    .panel{
        width: 100%;
        max-width: 440px;
        padding: 16px 20px;
        border-radius: 12px;
        background: rgba(0,3,20,0.60);
        border: 2px solid rgba(0,220,255,0.55);
        box-shadow: 0 0 26px rgba(0,220,255,0.7), inset 0 0 16px rgba(0,220,255,0.25);
        margin-top: 16px;
    }
    .panel-title{
        font-weight: 950;
        font-size: 20px;
        letter-spacing: 0.6px;
        margin-bottom: 12px;
        text-shadow: 0 0 14px rgba(0,220,255,0.7);
    }

    .xp-row{
        display: flex;
        justify-content: space-between;
        gap: 14px;
        padding: 6px 0;
        border-bottom: 1px solid rgba(0,220,255,0.12);
        font-size: 15px;
    }
    .xp-name{ opacity: 0.95; font-weight: 800; }
    .xp-val{ opacity: 0.95; font-weight: 950; color: rgba(180,255,255,0.95); text-shadow: 0 0 10px rgba(0,220,255,0.35); }
    .xp-val-debt{ opacity: 0.95; font-weight: 950; color: rgba(255,140,140,0.95); text-shadow: 0 0 10px rgba(255,80,80,0.35); }

    .menu-header{
        width: 100%;
        max-width: 440px;
        margin-top: 10px;
        margin-bottom: 8px;
        font-weight: 950;
        font-size: 20px;
        letter-spacing: 0.6px;
        text-shadow: 0 0 14px rgba(0,220,255,0.7);
    }

    div[data-testid="stSelectbox"] div[role="combobox"]{
        border-radius: 12px !important;
        background: rgba(0,3,20,0.55) !important;
        border: 2px solid rgba(0,220,255,0.55) !important;
        box-shadow: 0 0 18px rgba(0,220,255,0.55),
                    inset 0 0 12px rgba(0,220,255,0.20) !important;
        color: #e8fbff !important;
        min-height: 44px !important;
    }
    div[data-testid="stSelectbox"] div[role="combobox"] *{
        color: #e8fbff !important;
        font-weight: 900 !important;
    }

    div[data-testid="stNumberInput"] input{
        border-radius: 12px !important;
        background: rgba(0,3,20,0.55) !important;
        border: 2px solid rgba(0,220,255,0.55) !important;
        box-shadow: 0 0 18px rgba(0,220,255,0.55),
                    inset 0 0 12px rgba(0,220,255,0.20) !important;
        color: #e8fbff !important;
        font-weight: 900 !important;
        min-height: 44px !important;
    }

    [data-testid="stWidgetLabel"] label,
    [data-testid="stWidgetLabel"] > label,
    label,
    label *{
        color: rgba(255,255,255,0.98) !important;
        font-weight: 900 !important;
        text-shadow: 0 0 10px rgba(0,220,255,0.45) !important;
    }

    div[data-testid="stButton"] > button{
        width: 100%;
        border-radius: 12px !important;
        background: rgba(0,3,20,0.55) !important;
        border: 2px solid rgba(0,220,255,0.55) !important;
        box-shadow: 0 0 18px rgba(0,220,255,0.55),
                    inset 0 0 12px rgba(0,220,255,0.20) !important;
        color: #e8fbff !important;
        font-weight: 950 !important;
        letter-spacing: 0.5px;
        padding: 10px 14px !important;
        min-height: 44px !important;
    }
    div[data-testid="stButton"] > button:hover{
        border: 2px solid rgba(0,255,255,0.85) !important;
        box-shadow: 0 0 24px rgba(0,255,255,0.75),
                    inset 0 0 14px rgba(0,255,255,0.25) !important;
    }
    div[data-testid="stButton"] > button:active{
        transform: translateY(1px);
    }

    [data-testid="stVerticalBlockBorderWrapper"]{
        border-radius: 12px !important;
        background: rgba(0,3,20,0.60) !important;
        border: 2px solid rgba(0,220,255,0.55) !important;
        box-shadow: 0 0 26px rgba(0,220,255,0.7), inset 0 0 16px rgba(0,220,255,0.25) !important;
        padding: 14px 16px !important;
    }

    @media (max-width: 900px){
        .hud-title{ text-align: center; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- XP TOTAL + LEVEL SYSTEM OUTPUT ----------
xp_total = float(sum(st.session_state.xp_values.values()))
debt_total = float(sum(st.session_state.debt_values.values()))

level, xp_in_level_int, xp_required = compute_level(xp_total, MAX_LEVEL)
title = title_for_level(level)

# XP gain bar shows decimals
whole_used_for_leveling = float(int(math.floor(xp_total)))
fractional_part = float(xp_total - whole_used_for_leveling)
xp_in_level_display = float(xp_in_level_int + fractional_part)

xp_pct = 0 if xp_required <= 0 else max(0, min(100, (xp_in_level_display / xp_required) * 100))

title_next = title_next_threshold(level)
title_pct = 0 if title_next <= 0 else max(0, min(100, (level / title_next) * 100))

# Debt bar (separate)
DEBT_CAP = 100.0
debt_pct = 0 if DEBT_CAP <= 0 else max(0, min(100, (debt_total / DEBT_CAP) * 100))

# ---------- MAIN LAYOUT ----------
col_char, col_hud, col_panel = st.columns([1, 2, 1], vertical_alignment="top")

with col_char:
    st.image("profile_photo.png", use_container_width=True)

with col_hud:
    st.markdown('<div class="hud-title">PLAYER HUD</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="hud-box">
        <strong>Name:</strong> Random<br>
        <strong>Age:</strong> Random<br>
        <strong>DOB:</strong> Random<br>
        <strong>Region:</strong> Random<br>
        <strong>Height:</strong> Random<br>
        <strong>Weight:</strong> Random
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="progress-box">
          <strong>Level:</strong> {level}<br>
          <strong>XP:</strong> {xp_total:.1f}<br>
          <strong>Title:</strong> {title}<br>

          <div class="bar-label">XP Gain</div>
          <div class="glow-bar">
            <div class="glow-bar-fill" style="width:{xp_pct}%;"></div>
            <div class="glow-bar-text">{xp_in_level_display:.1f}/{xp_required:.1f}</div>
          </div>

          <div class="bar-label">Title Gain</div>
          <div class="glow-bar">
            <div class="glow-bar-fill" style="width:{title_pct}%;"></div>
            <div class="glow-bar-text">{level}/{title_next}</div>
          </div>

          <div class="bar-label">XP Debt</div>
          <div class="glow-bar">
            <div class="glow-bar-fill-red" style="width:{debt_pct}%;"></div>
            <div class="glow-bar-text glow-bar-text-red">{debt_total:.1f}/{DEBT_CAP:.1f}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_panel:
    menu_options = [
        "XP Breakdown",
        "XP wall debt",
        "Physical Stats",
        "Mental Stats",
        "Social Stats",
        "Skill Stats",
        "Tools",
        "Rule Book",
    ]

    st.markdown('<div class="menu-header">Menu</div>', unsafe_allow_html=True)

    current_index = menu_options.index(st.session_state.section) if st.session_state.section in menu_options else 0
    picked = st.selectbox(
        label="",
        options=menu_options,
        index=current_index,
        key="menu_select",
        label_visibility="collapsed",
    )
    if picked != st.session_state.section:
        st.session_state.section = picked
        st.rerun()

    section = st.session_state.section

    if section == "XP Breakdown":
        xp_items = list(DEFAULT_XP_VALUES.keys())

        rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{item}</div>
                <div class="xp-val">{st.session_state.xp_values[item]:.1f} XP</div>
            </div>
            """
            for item in xp_items
        )

        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">XP Breakdown</div>
                {rows_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown('<div class="panel-title">Adjust XP</div>', unsafe_allow_html=True)

            adjust_cat = st.selectbox("Category", list(DEFAULT_XP_VALUES.keys()), key="adjust_cat")

            c1, c2 = st.columns([1, 2])
            adjust_mode = c1.selectbox("Mode", ["Add", "Minus"], key="adjust_mode")
            adjust_amt = c2.number_input(
                "Amount",
                min_value=0.0,
                max_value=100.0,
                value=0.2,
                step=0.2,
                format="%.1f",
                key="adjust_amt",
            )

            if st.button("Apply", key="apply_adjust"):
                delta = float(adjust_amt) if adjust_mode == "Add" else -float(adjust_amt)
                st.session_state.xp_values[adjust_cat] = max(
                    0.0,
                    float(st.session_state.xp_values[adjust_cat]) + delta,
                )
                try:
                    cloud_save_state(st.session_state.xp_values, st.session_state.debt_values)
                except Exception as e:
                    st.error(f"Cloud save failed: {e}")
                st.rerun()

        if st.button("Reset XP to defaults", key="reset_xp_bottom"):
            st.session_state.xp_values = DEFAULT_XP_VALUES.copy()
            try:
                cloud_save_state(st.session_state.xp_values, st.session_state.debt_values)
            except Exception as e:
                st.error(f"Cloud save failed: {e}")
            st.rerun()

    elif section == "XP wall debt":
        debt_items = list(DEFAULT_DEBT_VALUES.keys())

        rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{item}</div>
                <div class="xp-val-debt">{st.session_state.debt_values[item]:.1f}</div>
            </div>
            """
            for item in debt_items
        )

        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">XP wall debt</div>
                {rows_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown('<div class="panel-title">Adjust Debt</div>', unsafe_allow_html=True)

            debt_cat = st.selectbox("Category", list(DEFAULT_DEBT_VALUES.keys()), key="debt_cat")

            d1, d2 = st.columns([1, 2])
            debt_mode = d1.selectbox("Mode", ["Add", "Minus"], key="debt_mode")
            debt_amt = d2.number_input(
                "Amount",
                min_value=0.0,
                max_value=100.0,
                value=0.2,
                step=0.2,
                format="%.1f",
                key="debt_amt",
            )

            if st.button("Apply", key="apply_debt"):
                delta = float(debt_amt) if debt_mode == "Add" else -float(debt_amt)
                st.session_state.debt_values[debt_cat] = max(
                    0.0,
                    float(st.session_state.debt_values[debt_cat]) + delta,
                )
                try:
                    cloud_save_state(st.session_state.xp_values, st.session_state.debt_values)
                except Exception as e:
                    st.error(f"Cloud save failed: {e}")
                st.rerun()

        if st.button("Reset Debt to defaults", key="reset_debt_bottom"):
            st.session_state.debt_values = DEFAULT_DEBT_VALUES.copy()
            try:
                cloud_save_state(st.session_state.xp_values, st.session_state.debt_values)
            except Exception as e:
                st.error(f"Cloud save failed: {e}")
            st.rerun()

    elif section == "Physical Stats":
        physical_rows = [
            ("PUSH", 45),
            ("PULL", 62),
            ("SPD", 38),
            ("STM", 58),
            ("DUR", 70),
            ("BAL", 74),
            ("FLX", 38),
            ("RFLX", 50),
            ("POW", 40),
        ]
        rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{code}</div>
                <div class="xp-val">{lvl}/100</div>
            </div>
            """
            for code, lvl in physical_rows
        )
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">Physical Stats</div>
                {rows_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif section == "Mental Stats":
        mental_rows = [
            ("LRN", 65),
            ("LOG", 55),
            ("MEM", 58),
            ("STRAT", 60),
            ("FOCUS", 54),
            ("CREAT", 72),
            ("AWARE", 50),
            ("JUDG", 53),
            ("CALM", 42),
        ]
        rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{code}</div>
                <div class="xp-val">{lvl}/100</div>
            </div>
            """
            for code, lvl in mental_rows
        )
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">Mental Stats</div>
                {rows_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif section == "Social Stats":
        social_rows = [
            ("SOC", 46),
            ("LEAD", 48),
            ("NEG", 52),
            ("COM", 50),
            ("EMP", 32),
            ("PRES", 47),
        ]
        rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{code}</div>
                <div class="xp-val">{lvl}/100</div>
            </div>
            """
            for code, lvl in social_rows
        )
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">Social Stats</div>
                {rows_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif section == "Skill Stats":
        skill_rows = [
            ("CHESS", 68),
            ("ITALIAN", 12),
            ("JIUJITSU", 22),
        ]
        rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{code}</div>
                <div class="xp-val">{lvl}/100</div>
            </div>
            """
            for code, lvl in skill_rows
        )
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">Skill Stats</div>
                {rows_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:
        st.markdown(
            f"""
            <div class="panel">
              <div class="panel-title">{section}</div>
              <div style="opacity:0.85; font-weight:700;">
                Select a section from the Menu dropdown above.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
