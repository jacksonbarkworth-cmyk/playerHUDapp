import streamlit as st
import math
import requests
import textwrap
import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Player HUD", layout="wide")

# ---------- TIMEZONE ----------
USER_TZ = ZoneInfo("Europe/London")

def _parse_iso_dt(s):
    if not s or not isinstance(s, str):
        return None
    try:
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None

def fmt_log_dt_from_payload(payload):
    ts = (payload or {}).get("_ts_utc")
    dt = _parse_iso_dt(ts)
    if not dt:
        return "??:?? - ??.??.????"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(USER_TZ)
    return local.strftime("%H:%M - %d.%m.%Y")

def with_ts(p):
    p = dict(p or {})
    p["_ts_utc"] = datetime.now(timezone.utc).isoformat()
    return p

# ---------- STATE ----------
if "section" not in st.session_state:
    st.session_state.section = "XP Breakdown"

if st.session_state.section in ["XP wall debt", "XP wall Debt"]:
    st.session_state.section = "XP Wall Debt"

# ---------- XP BREAKDOWN DEFAULTS (SOURCE OF TRUTH) ----------
DEFAULT_XP_VALUES = {
    "Admin Work": 0.0,
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
    "Quest 3": 0.0,
    "Chess Streak": 0.0,
    "Italian Streak": 0.0,
    "Gym Streak": 0.0,
    "Jiu Jitsu Streak": 0.0,
    "Eating Healthy": 0.0,
    "Meet Hydration target": 0.0,
}

# ---------- XP RULES ----------
XP_PER_HOUR = {
    "Admin Work": 0.5,
    "Design Work": 1.0,
    "Jiu Jitsu Training": 4.0,
    "Gym Workout": 3.0,
    "Italian Studying": 2.0,
    "Italian Passive listening": 0.2,
    "Chess - Rated Matches": 2.0,
    "Chess - Study/ Analysis": 1.0,
    "Reading": 1.5,
    "New Skill Learning": 2.4,
    "Personal Challenge Quest": 3.6,
    "Recovery": 1.6,
    "Creative Output": 2.0,
    "General Life Task": 0.8,
}
XP_COMPLETION = {"Quest 1": 3.0, "Quest 2": 2.0, "Quest 3": 1.0}
XP_STREAK = {
    "Chess Streak": 1.0,
    "Italian Streak": 1.0,
    "Gym Streak": 1.0,
    "Jiu Jitsu Streak": 1.0,
    "Eating Healthy": 1.0,
    "Meet Hydration target": 1.0,
}


def xp_delta_from_choice(category: str, choice: str) -> float:
    if category in XP_PER_HOUR:
        rate = float(XP_PER_HOUR[category])
        if choice == "30 min":
            return rate * 0.5
        if choice == "1 hour":
            return rate * 1.0
        return 0.0
    if category in XP_COMPLETION:
        return float(XP_COMPLETION[category])
    if category in XP_STREAK:
        return float(XP_STREAK[category])
    return 0.0


# ---------- XP WALL DEBT DEFAULTS (SHORT NAMES, 3 WORDS MAX) ----------
OATH_KEYS = [
    "Oath: No Cheating",
    "Oath: No Betrayal of Trust",
    "Oath: No Stealing",
    "Oath: No Harm Defenseless",
    "Oath: No Malicious Exploit",
    "Oath: Honor Commitments",
    "Oath: Compete w/ Integrity",
    "Oath: Accountability",
    "Oath: No Sabotage Others",
]

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
    # --- OATH DEBT ITEMS (each Add = +6 XP debt) ---
    "Oath: No Cheating": 0.0,
    "Oath: No Betrayal of Trust": 0.0,
    "Oath: No Stealing": 0.0,
    "Oath: No Harm Defenseless": 0.0,
    "Oath: No Malicious Exploit": 0.0,
    "Oath: Honor Commitments": 0.0,
    "Oath: Compete w/ Integrity": 0.0,
    "Oath: Accountability": 0.0,
    "Oath: No Sabotage Others": 0.0,
}

DEBT_PENALTY = {
    "Skip Training": 2.0,
    "Junk Eating": 2.0,
    "Drug Use": 5.0,
    "Blackout Drunk": 3.0,
    "Reckless Driving": 4.0,
    "Start Fight": 3.0,
    "Doomscrolling": 1.5,
    "Miss Work": 4.0,
    "Impulsive Spend": 2.5,
    "Malicious Deceit": 2.0,
    "Break Oath": 6.0,
    "All Nighter": 2.0,
    "Avoid Duty": 2.0,
    "Ignore Injury": 2.5,
    "Miss Hydration": 1.0,
    "Sleep Collapse": 2.0,
    "Ghost Obligation": 3.5,
    "Ego Decisions": 2.0,
    "No Logging": 1.0,
    "Message Pile": 1.5,
    "Quest Miss": 3.0,
    # --- OATH PENALTIES (each Add = +6 XP debt) ---
    "Oath: No Cheating": 6.0,
    "Oath: No Betrayal of Trust": 6.0,
    "Oath: No Stealing": 6.0,
    "Oath: No Harm Defenseless": 6.0,
    "Oath: No Malicious Exploit": 6.0,
    "Oath: Honor Commitments": 6.0,
    "Oath: Compete w/ Integrity": 6.0,
    "Oath: Accountability": 6.0,
    "Oath: No Sabotage Others": 6.0,
}

# ---------- STATS DEFAULTS ----------
DEFAULT_PHYSICAL = {"PUSH": 0, "PULL": 0, "SPD": 0, "STM": 0, "DUR": 0, "BAL": 0, "FLX": 0, "RFLX": 0, "POW": 0}
DEFAULT_MENTAL = {"LRN": 0, "LOG": 0, "MEM": 0, "STRAT": 0, "FOCUS": 0, "CREAT": 0, "AWARE": 0, "JUDG": 0, "CALM": 0}
DEFAULT_SOCIAL = {"SOC": 0, "LEAD": 0, "NEG": 0, "COM": 0, "EMP": 0, "PRES": 0}
DEFAULT_SKILL = {"CHESS": 0, "ITALIAN": 0, "JIUJITSU": 0}

DEFAULT_STATS = {
    "Physical": DEFAULT_PHYSICAL,
    "Mental": DEFAULT_MENTAL,
    "Social": DEFAULT_SOCIAL,
    "Skill": DEFAULT_SKILL,
}

# ---------- HELPERS ----------
def fmt_xp(x: float, max_decimals: int = 2) -> str:
    try:
        x = float(x)
    except Exception:
        x = 0.0
    s = f"{x:.{max_decimals}f}".rstrip("0").rstrip(".")
    return s if s else "0"

def fmt_log_dt_from_payload(payload: dict) -> str:
    ts = (payload or {}).get("_ts_utc")
    dt = _parse_iso_dt(ts)
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(USER_TZ)
    return local.strftime("%H:%M - %d.%m.%Y")

def coerce_and_align_keep_meta(loaded: dict, defaults: dict) -> dict:
    """
    Aligns to defaults, coerces to float.
    Keeps any meta keys that start with '__' (used to persist extra data).
    """
    loaded = loaded or {}
    out = {}
    for k, dv in defaults.items():
        try:
            out[k] = float(loaded.get(k, dv))
        except Exception:
            out[k] = float(dv)

    # keep meta keys
    for k, v in loaded.items():
        if isinstance(k, str) and k.startswith("__"):
            out[k] = v
    return out


def coerce_int_dict(loaded: dict, defaults: dict) -> dict:
    loaded = loaded or {}
    out = {}
    for k, dv in defaults.items():
        try:
            out[k] = int(loaded.get(k, dv))
        except Exception:
            out[k] = int(dv)
        out[k] = max(0, min(100, out[k]))
    return out


def apply_xp_with_debt_payment(xp_gain: float) -> float:
    """
    Pays down XP Wall Debt first using earned XP.
    Returns leftover XP after debt is reduced.
    Reduces debt proportionally across categories.
    """
    xp_gain = float(max(0.0, xp_gain))
    if xp_gain <= 0:
        return 0.0

    total_debt = float(sum(st.session_state.debt_values.values()))
    if total_debt <= 0:
        return xp_gain

    pay = min(xp_gain, total_debt)
    remaining_pay = pay

    # proportional reduction
    for k, v in list(st.session_state.debt_values.items()):
        v = float(v)
        if v <= 0 or remaining_pay <= 0:
            continue
        share = (v / total_debt) * pay
        reduction = min(v, share)
        st.session_state.debt_values[k] = float(max(0.0, v - reduction))
        remaining_pay -= reduction

    # cleanup
    if remaining_pay > 1e-6:
        for k, v in list(st.session_state.debt_values.items()):
            if remaining_pay <= 0:
                break
            v = float(v)
            if v <= 0:
                continue
            reduction = min(v, remaining_pay)
            st.session_state.debt_values[k] = float(max(0.0, v - reduction))
            remaining_pay -= reduction

    return float(xp_gain - pay)


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
    for t, lo, hi in TITLE_RANGES:
        if lo <= level <= hi:
            return t
    return "Unranked"

def title_next_threshold(level: int) -> int:
    for _t, lo, hi in TITLE_RANGES:
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


def compute_derived_state_now() -> dict:
    xp_total_now = float(sum(st.session_state.xp_values[k] for k in DEFAULT_XP_VALUES.keys()))
    debt_total_now = float(sum(st.session_state.debt_values[k] for k in DEFAULT_DEBT_VALUES.keys()))
    effective_xp_now = max(0.0, xp_total_now - debt_total_now)
    lvl_now, _xin, _req = compute_level(effective_xp_now, MAX_LEVEL)
    ttl_now = title_for_level(lvl_now)
    return {
        "xp_total": float(xp_total_now),
        "debt_total": float(debt_total_now),
        "effective_xp": float(effective_xp_now),
        "level": int(lvl_now),
        "title": str(ttl_now),
    }

def get_prev_derived_state() -> dict:
    meta = {}
    if isinstance(st.session_state.get("xp_values", {}), dict):
        meta = st.session_state.xp_values.get("__last_derived__", {}) or {}
    return meta if isinstance(meta, dict) else {}

def set_prev_derived_state(state: dict):
    if isinstance(st.session_state.get("xp_values", {}), dict):
        st.session_state.xp_values["__last_derived__"] = state


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

    def cloud_append_log(event_type: str, payload: dict, snapshot=None):
        url = f"{SUPABASE_URL}/rest/v1/player_state_log"
        row = {
            "save_key": SAVE_KEY,
            "event_type": event_type,
            "payload": payload or {},
            "snapshot": snapshot,
        }
        r = requests.post(url, headers=_SB_HEADERS, json=row, timeout=15)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase log append failed ({r.status_code}): {r.text}")

    def cloud_load_logs(limit=500):
        url = f"{SUPABASE_URL}/rest/v1/player_state_log"

        attempts = [
            {
                "params": {
                    "save_key": f"eq.{SAVE_KEY}",
                    "select": "id,event_type,payload",
                    "order": "id.desc",
                    "limit": str(limit),
                }
            },
            {
                "params": {
                    "save_key": f"eq.{SAVE_KEY}",
                    "select": "event_type,payload",
                    "limit": str(limit),
                }
            },
        ]

        last_err = None
        for a in attempts:
            r = requests.get(url, headers=_SB_HEADERS, params=a["params"], timeout=15)
            if r.status_code < 400:
                return r.json()
            last_err = r.text

        raise RuntimeError(f"Supabase log load failed: {last_err}")
        return r.json()

else:
    def cloud_load_state():
        return None

    def cloud_save_state(xp_values, debt_values):
        return None

    def cloud_append_log(event_type, payload, snapshot=None):
        return None

    def cloud_load_logs(limit=500):
        return []

        last_err = None
        for a in attempts:
            r = requests.get(url, headers=_SB_HEADERS, params=a["params"], timeout=15)
            if r.status_code < 400:
                return r.json()
            last_err = r.text

        raise RuntimeError(f"Supabase log load failed: {last_err}")

def ensure_stats_in_session_from_meta():
    meta = st.session_state.xp_values.get("__stats__", {}) if isinstance(st.session_state.xp_values, dict) else {}
    if "stats" not in st.session_state:
        st.session_state.stats = {k: v.copy() for k, v in DEFAULT_STATS.items()}

    # load from meta if present
    if isinstance(meta, dict) and meta:
        for group, defaults in DEFAULT_STATS.items():
            loaded_group = meta.get(group, {})
            st.session_state.stats[group] = coerce_int_dict(loaded_group, defaults)


def write_stats_to_meta_before_save():
    # store stats inside xp_values meta to persist without changing DB schema
    if "stats" not in st.session_state:
        return
    st.session_state.xp_values["__stats__"] = {
        "Physical": st.session_state.stats.get("Physical", {}).copy(),
        "Mental": st.session_state.stats.get("Mental", {}).copy(),
        "Social": st.session_state.stats.get("Social", {}).copy(),
        "Skill": st.session_state.stats.get("Skill", {}).copy(),
    }

def save_all(event_type=None, payload=None, include_snapshot=False):
    write_stats_to_meta_before_save()

    prev = get_prev_derived_state()
    now = compute_derived_state_now()

    # 1) append log first
    if CLOUD_ENABLED and event_type:
        snap = None
        if include_snapshot:
            snap = {
                "xp_values": st.session_state.xp_values,
                "debt_values": st.session_state.debt_values,
            }

        try:
            cloud_append_log(event_type, with_ts(payload), snapshot=snap)

            if isinstance(prev, dict) and prev:
                if str(now.get("title")) != str(prev.get("title")):
                    cloud_append_log("title_unlocked", with_ts({"title": now.get("title")}), snapshot=None)

                if int(now.get("level", 0)) > int(prev.get("level", 0)):
                    cloud_append_log(
                        "level_up",
                        with_ts({"from": int(prev.get("level", 0)), "to": int(now.get("level", 0))}),
                        snapshot=None,
                    )
        except Exception as e:
            st.error(f"Cloud log failed: {e}")

    # store derived state in meta BEFORE saving
    set_prev_derived_state(now)

    # 2) save snapshot
    try:
        cloud_save_state(st.session_state.xp_values, st.session_state.debt_values)
    except Exception as e:
        st.error(f"Cloud save failed: {e}")

    # store last derived state in meta
    set_prev_derived_state(now)

    # 2) save current snapshot
    try:
        cloud_save_state(st.session_state.xp_values, st.session_state.debt_values)
    except Exception as e:
        st.error(f"Cloud save failed: {e}")

    # update last derived state (stored in meta) BEFORE saving state
    set_prev_derived_state(now)

    # 2) save current snapshot
    try:
        cloud_save_state(st.session_state.xp_values, st.session_state.debt_values)
    except Exception as e:
        st.error(f"Cloud save failed: {e}")


def reset_all():
    st.session_state.xp_values = DEFAULT_XP_VALUES.copy()
    st.session_state.debt_values = DEFAULT_DEBT_VALUES.copy()
    st.session_state.stats = {k: v.copy() for k, v in DEFAULT_STATS.items()}
    save_all(
        event_type="reset",
        payload={"reason": "user_clicked_reset_all"},
        include_snapshot=True,
    )
    st.rerun()


# ---------- CLOUD INIT ----------
if "xp_values" not in st.session_state or "debt_values" not in st.session_state:
    try:
        loaded = cloud_load_state()
    except Exception as e:
        st.warning(f"Cloud sync unavailable. Using local defaults for this session.\n\nDetails: {e}")
        loaded = None

    if loaded is None:
        st.session_state.xp_values = DEFAULT_XP_VALUES.copy()
        st.session_state.debt_values = DEFAULT_DEBT_VALUES.copy()
        st.session_state.stats = {k: v.copy() for k, v in DEFAULT_STATS.items()}
        save_all()
    else:
        xp_loaded, debt_loaded = loaded
        st.session_state.xp_values = coerce_and_align_keep_meta(xp_loaded, DEFAULT_XP_VALUES)
        st.session_state.debt_values = coerce_and_align_keep_meta(debt_loaded, DEFAULT_DEBT_VALUES)
        ensure_stats_in_session_from_meta()

# Always align (prevents KeyError if old cloud state exists)
st.session_state.xp_values = coerce_and_align_keep_meta(st.session_state.get("xp_values", {}), DEFAULT_XP_VALUES)
st.session_state.debt_values = coerce_and_align_keep_meta(st.session_state.get("debt_values", {}), DEFAULT_DEBT_VALUES)
ensure_stats_in_session_from_meta()

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
        padding-top: 22px !important;
        padding-bottom: 22px !important;
        padding-left: 10px !important;
        padding-right: 10px !important;
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

    /* Make ALL widget labels white */
    [data-testid="stWidgetLabel"] label,
    [data-testid="stWidgetLabel"] > label,
    label,
    label *{
        color: rgba(255,255,255,0.98) !important;
        font-weight: 900 !important;
        text-shadow: 0 0 10px rgba(0,220,255,0.45) !important;
    }

    /* Selectbox styling */
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
    /* click-only selectbox (hide typing) */
    div[data-testid="stSelectbox"] input{
        opacity: 0 !important;
        height: 0px !important;
        padding: 0 !important;
        margin: 0 !important;
        border: 0 !important;
    }

    /* Buttons */
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

    /* Settings expander arrow -> black + bold-ish */
    div[data-testid="stExpander"] summary svg {
        stroke: #000 !important;
        stroke-width: 3px !important;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 950 !important;
    }

    @media (max-width: 600px){
        .hud-title{
            font-size: 26px !important;
            text-align: center;
            margin-bottom: 10px;
        }
        .hud-box, .progress-box, .panel{
            max-width: 100% !important;
            padding: 10px 12px !important;
            font-size: 13px !important;
            border-width: 1.4px !important;
            margin-bottom: 10px !important;
        }
        .panel-title{
            font-size: 15px !important;
            margin-bottom: 6px !important;
        }
        .xp-row{
            font-size: 13px !important;
            padding: 4px 0 !important;
            gap: 8px !important;
        }
        .glow-bar{
            height: 16px !important;
            margin-top: 5px !important;
        }
        div[data-testid="stButton"] > button{
            font-size: 12px !important;
            padding: 6px 8px !important;
            min-height: 34px !important;
        }
        div[data-testid="stSelectbox"] div[role="combobox"]{
            font-size: 12px !important;
            min-height: 34px !important;
            padding: 4px 8px !important;
        }
        div[data-testid="stSelectbox"] ul{
            font-size: 12px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- XP TOTAL + LEVEL SYSTEM OUTPUT ----------
xp_total = float(sum(st.session_state.xp_values[k] for k in DEFAULT_XP_VALUES.keys()))
debt_total = float(sum(st.session_state.debt_values[k] for k in DEFAULT_DEBT_VALUES.keys()))

debt_warning = (
    ' <span style="color: rgba(255,90,90,0.95); font-weight: 950;">(Clear debt before gaining XP)</span>'
    if debt_total > 0
    else ""
)

# RULE: progression uses effective XP
effective_xp = max(0.0, xp_total - debt_total)

# Level + title are based on effective XP (rule)
level, _xp_in_level_effective, _xp_required_effective = compute_level(effective_xp, MAX_LEVEL)
title = title_for_level(level)

# Raw level (for UI bars that should NOT move when debt changes)
level_raw, _xp_in_level_raw_for_title, _xp_required_raw_for_title = compute_level(xp_total, MAX_LEVEL)

# Title bar values (you already had these)
title_next_raw = title_next_threshold(level_raw)
title_pct = 0 if title_next_raw <= 0 else max(0, min(100, (level_raw / title_next_raw) * 100))

# XP Gain bar should NOT be affected by debt
# Level is still based on floored effective XP rules (compute_level floors internally)
level_raw, _xin_raw_int, xp_required_raw = compute_level(xp_total, MAX_LEVEL)

# Total XP required to reach the START of current level (sum_{l=1}^{level-1} l*10)
xp_spent_before_level = 10.0 * (level_raw - 1) * level_raw / 2.0

# XP inside level uses RAW xp_total so decimals show
xp_in_level_display = max(0.0, float(xp_total) - xp_spent_before_level)

xp_required_display = float(xp_required_raw)

# Clamp inside-level XP so bar never overflows
xp_in_level_display = min(xp_in_level_display, xp_required_display)

xp_pct = 0.0 if xp_required_display <= 0 else max(
    0.0, min(100.0, (xp_in_level_display / xp_required_display) * 100.0)
)

DEBT_CAP = 100.0
debt_pct = 0 if DEBT_CAP <= 0 else max(0, min(100, (debt_total / DEBT_CAP) * 100))

# ---------- MAIN LAYOUT ----------
col_hud, col_panel = st.columns([2, 1], vertical_alignment="top")

with col_hud:
    st.markdown('<div class="hud-title">PLAYER HUD</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="hud-box">
        <strong>Name:</strong> Jackson Barkworth<br>
        <strong>Age:</strong> 22<br>
        <strong>DOB:</strong> 06/11/2003<br>
        <strong>Region:</strong> United Kingdom<br>
        <strong>Height:</strong> 5'9<br>
        <strong>Weight:</strong> 14 Stone
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="progress-box">
          <strong>Level:</strong> {level}<br>
          <strong>XP:</strong> {fmt_xp(xp_total)}<br>
          <strong>Title:</strong> {title}<br>

          <div class="bar-label">XP Gain</div>
          <div class="glow-bar">
            <div class="glow-bar-fill" style="width:{xp_pct}%;"></div>
            <div class="glow-bar-text">{fmt_xp(xp_in_level_display)}/{fmt_xp(xp_required_display)}</div>
          </div>

          <div class="bar-label">Title Gain</div>
          <div class="glow-bar">
            <div class="glow-bar-fill" style="width:{title_pct}%;"></div>
            <div class="glow-bar-text">{level_raw}/{title_next_raw}</div>
          </div>

          <div class="bar-label">XP Debt{debt_warning}</div>
          <div class="glow-bar">
            <div class="glow-bar-fill-red" style="width:{debt_pct}%;"></div>
            <div class="glow-bar-text glow-bar-text-red">{fmt_xp(debt_total)}/{fmt_xp(DEBT_CAP)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_panel:
    menu_options = [
        "XP Breakdown",
        "XP Wall Debt",
        "Physical Stats",
        "Mental Stats",
        "Social Stats",
        "Skill Stats",
        "Tools & Gear",
        "Rule Book",
        "Log",  # <-- needed so the Settings button can navigate without snapping back
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

    # -------- XP BREAKDOWN --------
    if section == "XP Breakdown":
        xp_items = list(DEFAULT_XP_VALUES.keys())

        rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{item}</div>
                <div class="xp-val">{fmt_xp(st.session_state.xp_values[item])} XP</div>
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

        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">Adjust XP</div>', unsafe_allow_html=True)

        c_cat, c_mode, c_time, c_apply = st.columns([3, 2, 2.4, 1.6])

        with c_cat:
            adjust_cat = st.selectbox("Category", list(DEFAULT_XP_VALUES.keys()), key="adjust_cat")

        with c_mode:
            adjust_mode = st.selectbox("Mode", ["Add", "Minus"], key="adjust_mode")

        with c_time:
            if adjust_cat in XP_PER_HOUR:
                time_choice = st.selectbox("Time", ["30 min", "1 hour"], key="xp_time_choice")
            elif adjust_cat in XP_COMPLETION:
                time_choice = st.selectbox("Time", ["Completion"], key="xp_time_choice")
            elif adjust_cat in XP_STREAK:
                time_choice = st.selectbox("Time", ["+1 (streak/day)"], key="xp_time_choice")
            else:
                time_choice = st.selectbox("Time", ["N/A"], key="xp_time_choice")

        with c_apply:
            apply_clicked = st.button("Apply", key="apply_adjust")

        if apply_clicked:
            base = float(xp_delta_from_choice(adjust_cat, time_choice))
            leftover = None

            if adjust_mode == "Minus":
                st.session_state.xp_values[adjust_cat] = max(
                    0.0,
                    float(st.session_state.xp_values[adjust_cat]) - base
                )
            else:
                leftover = apply_xp_with_debt_payment(base)
                st.session_state.xp_values[adjust_cat] = max(
                    0.0,
                    float(st.session_state.xp_values[adjust_cat]) + float(leftover)
                )

            save_all(
                event_type="xp_adjust",
                payload={
                    "category": adjust_cat,
                    "mode": adjust_mode,
                    "time_choice": time_choice,
                    "base": base,
                    "leftover_after_debt": leftover,
                },
                include_snapshot=False,
            )
            st.rerun()

    # -------- XP WALL DEBT --------
    elif section == "XP Wall Debt":
        debt_items = list(DEFAULT_DEBT_VALUES.keys())

        normal_debt_items = [k for k in debt_items if k not in OATH_KEYS]
        oath_debt_items = [k for k in debt_items if k in OATH_KEYS]

        rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{item}</div>
                <div class="xp-val-debt">{fmt_xp(st.session_state.debt_values.get(item, 0.0))} XP</div>
            </div>
            """
            for item in normal_debt_items
        )

        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">XP Wall Debt</div>
                {rows_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        oath_rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{item}</div>
                <div class="xp-val-debt">{fmt_xp(st.session_state.debt_values.get(item, 0.0))} XP</div>
            </div>
            """
            for item in oath_debt_items
        )

        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">Oath Debt</div>
                {oath_rows_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">Adjust Debt</div>', unsafe_allow_html=True)

        d_cat, d_mode, d_apply = st.columns([5, 2, 1.8])

        with d_cat:
            debt_cat = st.selectbox("Category", list(DEFAULT_DEBT_VALUES.keys()), key="debt_cat")

        with d_mode:
            debt_mode = st.selectbox("Mode", ["Add", "Minus"], key="debt_mode")

        with d_apply:
            debt_apply_clicked = st.button("Apply", key="apply_debt")

        if debt_apply_clicked:
            base = float(DEBT_PENALTY.get(debt_cat, 0.0))
            delta = base if debt_mode == "Add" else -base

            st.session_state.debt_values[debt_cat] = max(
                0.0,
                float(st.session_state.debt_values.get(debt_cat, 0.0)) + float(delta)
            )

            save_all(
                event_type="debt_adjust",
                payload={
                    "category": debt_cat,
                    "mode": debt_mode,
                    "delta": delta,
                    "base_penalty": base,
                },
                include_snapshot=False,
            )
            st.rerun()

    # -------- STATS SECTIONS --------
    def render_stats_panel(title_text: str, group_key: str, widget_prefix: str):
        stats_dict = st.session_state.stats.get(group_key, {}).copy()

        rows_html = "\n".join(
            f"""
            <div class="xp-row">
                <div class="xp-name">{code}</div>
                <div class="xp-val">{int(val)}/100</div>
            </div>
            """
            for code, val in stats_dict.items()
        )

        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">{title_text}</div>
                {rows_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="panel-title">Adjust {title_text}</div>', unsafe_allow_html=True)

        s_stat, s_mode, s_apply = st.columns([5, 2, 1.8])

        with s_stat:
            pick = st.selectbox("Stat", list(stats_dict.keys()), key=f"{widget_prefix}_stat")

        with s_mode:
            mode = st.selectbox("Mode", ["Add", "Minus"], key=f"{widget_prefix}_mode")

        with s_apply:
            go = st.button("Apply", key=f"{widget_prefix}_apply")

        if go:
            cur = int(st.session_state.stats[group_key].get(pick, 0))
            cur = cur + 1 if mode == "Add" else cur - 1
            cur = max(0, min(100, cur))
            st.session_state.stats[group_key][pick] = int(cur)
            save_all(
                event_type="stat_adjust",
                payload={
                    "group": group_key,
                    "stat": pick,
                    "mode": mode,
                    "new_value": int(cur),
                },
                include_snapshot=False,
            )
            st.rerun()

    if section == "Physical Stats":
        render_stats_panel("Physical Stats", "Physical", "phys")
    elif section == "Mental Stats":
        render_stats_panel("Mental Stats", "Mental", "ment")
    elif section == "Social Stats":
        render_stats_panel("Social Stats", "Social", "soc")
    elif section == "Skill Stats":
        render_stats_panel("Skill Stats", "Skill", "skill")

    # -------- LOG PAGE --------
    elif section == "Log":
        st.markdown(
            """
            <div class="panel">
            <div class="panel-title">Log</div>
            <div style="opacity:0.85; font-weight:800; line-height:1.6;">
                Closest date/time is shown at the top.
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        limit = st.selectbox("Show last", [50, 100, 200, 500, 1000], index=0, key="log_limit")

        logs = []
        if CLOUD_ENABLED:
            try:
                logs = cloud_load_logs(limit=int(limit))
            except Exception as e:
                st.error(f"Could not load logs: {e}")
                logs = []
        else:
            st.info("Cloud is disabled, so there are no logs to display.")

        def render_log_line(event_type: str, payload: dict) -> str:
            p = payload or {}
            ts = fmt_log_dt_from_payload(p)

            if event_type == "stat_adjust":
                group = p.get("group", "")
                mode = p.get("mode", "")
                newv = p.get("new_value", None)
                gain_word = "Gain" if mode == "Add" else "Loss"
                # matches your example format; shows new stat level
                if newv is not None:
                    return f"{ts} - {group} Stats {gain_word} by 1 ({int(newv)}/100)"
                return f"{ts} - {group} Stats {gain_word} by 1"

            if event_type == "xp_adjust":
                cat = p.get("category", "")
                mode = p.get("mode", "")
                base = p.get("base", 0.0)
                leftover = p.get("leftover_after_debt", None)
                amt = leftover if leftover is not None else base
                action = "XP Gain" if mode == "Add" else "XP Minus"
                return f"{ts} - {action} from {cat} ({fmt_xp(amt)} XP)"

            if event_type == "debt_adjust":
                cat = p.get("category", "")
                mode = p.get("mode", "")
                base_pen = p.get("base_penalty", None)
                delta = p.get("delta", 0.0)
                amt = base_pen if base_pen is not None else abs(delta)
                action = "XP Debt" if mode == "Add" else "Debt Minus"
                return f"{ts} - {action} from {cat} ({fmt_xp(amt)} XP)"

            if event_type == "level_up":
                fr = p.get("from", "")
                to = p.get("to", "")
                return f"{ts} - Level Increase from {fr} to {to}"

            if event_type == "title_unlocked":
                t = p.get("title", "")
                return f"{ts} - New Title Unlocked ({t})"

            if event_type == "reset":
                return f"{ts} - Reset"

            return f"{ts} - {event_type}"

        if not logs:
            st.info("No log entries yet.")
        else:
            lines = []
            for row in logs:
                event_type = row.get("event_type", "") or ""
                payload = row.get("payload", {}) or {}
                lines.append(render_log_line(event_type, payload))

            rows_html = "\n".join(
                f"""
                <div class="xp-row">
                    <div class="xp-name" style="font-weight:900;">{html.escape(line)}</div>
                </div>
                """
                for line in lines
            )

            st.markdown(
                f"""
                <div class="panel">
                    <div class="panel-title">Entries</div>
                    {rows_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # -------- Tools / Rule Book --------
    elif section == "Tools & Gear":
        st.markdown(
            """
            <div class="panel">
              <div class="panel-title">Tools & Gear</div>
              <div style="opacity:0.85; font-weight:800;">
                (Coming soon)
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif section == "Rule Book":
        rulebook_text = """**Core Rule**
- XP is progress currency.
- XP Wall Debt blocks progression.
- When XP is earned while debt exists, earned XP pays down debt first. Only leftover XP becomes real XP gain in the selected category.

---
#### 1) What This System Tracks (Actual)
- **XP (by category)**: your stored XP totals (can include decimals)
- **XP Wall Debt (by category)**: your stored debt totals (can include decimals)
- **Effective XP** = max(0, Total XP − Total Debt)
- **Level + Title (displayed)**: computed from **Effective XP**
- **XP Gain bar (UI)**: computed from **Raw Total XP** (NOT affected by debt)
- **Title Gain bar (UI)**: computed from **Raw Total XP** via the raw level (NOT affected by debt)
- **Stats**: manual attributes clamped 0–100

---
#### 2) XP & Debt Interaction (Actual Logic)
- **Effective XP = max(0, Total XP − Total Debt)**
- If **Total Debt > 0** and you **Add XP**, the system runs debt payoff first:
- It pays down debt **proportionally across ALL debt categories** based on each category’s share of total debt at the moment of payment.
- If tiny rounding remainder exists, a cleanup pass finishes paying down remaining debt until the payment amount is fully applied.
- Only the **leftover XP after debt payment** is added to your chosen XP category.
- If you **Minus XP**, it only reduces that XP category (never increases debt).

---
#### 3) Level System (Actual Logic)
- Level is computed using **floored integer XP**:
- The system uses int(floor(xp) before calculating levels (decimals do not count for level calculation).
- Level-up requirement for each step:
- Requirement to go from Level L to L+1 is **L × 10 XP**
- Computation method:
- Starting at Level 1, the system repeatedly subtracts the current requirement until it can’t.
- The leftover is your **XP inside the current level**.

---
#### 4) Titles by Level Range (Used for Displayed Title)
- Novice → Levels 1–5
- Trainee → Levels 6–10
- Adept → Levels 11–15
- Knight → Levels 16–20
- Champion → Levels 21–25
- Elite → Levels 26–30
- Legend → Levels 31–35
- Mythic → Levels 36–40
- Master → Levels 41–45
- Grandmaster → Levels 46–50
- Ascendant → Levels 51–55
- Exemplar → Levels 56–60
- Paragon → Levels 61–65
- Titan → Levels 66–70
- Sovereign → Levels 71–75
- Immortal-Seed → Levels 76–80
- Immortal → Levels 81–85
- Eternal-Seed → Levels 86–90
- Eternal → Levels 91–95
- World-Class → Levels 96–100

---
#### 5) What the 3 Bars Mean (Important UI Rules)
- **XP Gain bar**
- Shows progress inside your current level computed from **Raw Total XP**.
- **Debt does NOT move this bar.**
- **Title Gain bar**
- Shows progress toward the next title threshold using the **Raw Level** derived from **Raw Total XP**.
- **Debt does NOT move this bar.**
- **XP Debt bar**
- Shows Total Debt relative to **DEBT_CAP = 100**.
- This is display only; it does not change the other bars.

---
#### 6) XP Earnable Actions (Rates Used by the XP Adjust Tool)
Per-hour categories:
- Admin Work → 0.5 XP per hour
- Design Work → 1.0 XP per hour
- Gym Workout → 3.0 XP per hour
- Jiu Jitsu Training → 4.0 XP per hour
- Italian Studying → 2.0 XP per hour
- Italian Passive listening → 0.2 XP per hour
- Chess - Rated Matches → 2.0 XP per hour
- Chess - Study/ Analysis → 1.0 XP per hour
- Reading → 1.5 XP per hour
- New Skill Learning → 2.4 XP per hour
- Personal Challenge Quest → 3.6 XP per hour
- Recovery → 1.6 XP per hour
- Creative Output → 2.0 XP per hour
- General Life Task → 0.8 XP per hour

Quest completion categories:
- Quest 1 → +3.0 XP (Completion)
- Quest 2 → +2.0 XP (Completion)
- Quest 3 → +1.0 XP (Completion)

Streak categories:
- Chess Streak → +1.0 XP
- Italian Streak → +1.0 XP
- Gym Streak → +1.0 XP
- Jiu Jitsu Streak → +1.0 XP
- Eating Healthy → +1.0 XP
- Meet Hydration target → +1.0 XP

---
#### 7) XP Wall Debt Penalties (Used by the Debt Adjust Tool)
Normal debt categories (each Add applies the listed amount):
- Skip Training → 2.0 XP debt
- Junk Eating → 2.0 XP debt
- Drug Use → 5.0 XP debt
- Blackout Drunk → 3.0 XP debt
- Reckless Driving → 4.0 XP debt
- Start Fight → 3.0 XP debt
- Doomscrolling → 1.5 XP debt
- Miss Work → 4.0 XP debt
- Impulsive Spend → 2.5 XP debt
- Malicious Deceit → 2.0 XP debt
- Break Oath → 6.0 XP debt
- All Nighter → 2.0 XP debt
- Avoid Duty → 2.0 XP debt
- Ignore Injury → 2.5 XP debt
- Miss Hydration → 1.0 XP debt
- Sleep Collapse → 2.0 XP debt
- Ghost Obligation → 3.5 XP debt
- Ego Decisions → 2.0 XP debt
- No Logging → 1.0 XP debt
- Message Pile → 1.5 XP debt
- Quest Miss → 3.0 XP debt *(manual judgement; the system does not enforce conditions)*

Oath debt categories (each Add applies **+6.0 XP debt**):
- Oath: No Cheating
- Oath: No Betrayal of Trust
- Oath: No Stealing
- Oath: No Harm Defenseless
- Oath: No Malicious Exploit
- Oath: Honor Commitments
- Oath: Compete w/ Integrity
- Oath: Accountability
- Oath: No Sabotage Others

**Important:** The system currently allows both **Break Oath** and individual **Oath: ...** categories to be used. Avoid double-penalizing unless you intentionally want that.

---
#### 8) Stats (Actual Rules)
- Stats are stored under: Physical, Mental, Social, Skill.
- Stats are clamped to **0–100**.
- The Adjust Stats tool changes values by **±1** per click.

---
#### 9) Coin Economy (Design Only)
- £1 = 1 Coin
- £180 = 180 Coins
- £600/week = 600 Coins/week
- Coins are **not implemented** in the current code.
---
#### 10) Stats Meaning Scale (Design Lore)
- **-100** → extreme impairment / minimal motor-cognitive function
- **-50** → far below average adult
- **-40 to -10** → below-average adult variation band
- **0** → average untrained adult male baseline
- **+50** → trained competitive amateur
- **+65** → advanced regional amateur competitor
- **+80** → national competitor
- **+95** → elite international competitor
- **100** → best verified human performance
- Negative stats are **not active in code** unless range is expanded

---
#### 11) How to Measure Stats (Reference Benchmarks)
**Physical**
- **PUSH** → Max push-up test *(avg 25 reps)*
- **PULL** → Max pull-up test *(avg 2 reps)*
- **SPD** → 100m sprint test *(avg 16.5s)*
- **STM** → 5km run test *(avg 35 min)*
- **DUR** → Recovery benchmark after stress tests
- **BAL** → Single-leg stand test *(avg 45 sec)*
- **FLX** → Sit-and-reach test *(avg 30 cm)*
- **RFLX** → Visual reaction time *(avg 230 ms)*
- **POW** → Power output benchmark *(e.g., medicine ball throw distance)*

**Mental**
- **LRN** → Recall test after short structured learning
- **LOG** → Logic benchmark *(e.g., 20-question reasoning test)*
- **MEM** → Digit or item span recall benchmark
- **STRAT** → Scenario planning depth benchmark
- **FOCUS** → Continuous attention benchmark test
- **CREAT** → Originality or idea-generation benchmark
- **AWARE** → Observation & environment recall test
- **JUDG** → Scenario decision-quality scoring
- **CALM** → Accuracy + heart-rate under pressure

**Social**
- **SOC** → Social initiation & comfort benchmarks
- **LEAD** → Responsibility & group direction audit
- **NEG** → Negotiation/persuasion scenario benchmark
- **COM** → Explanation clarity & articulation scoring
- **EMP** → Emotion recognition & EQ benchmark
- **PRES** → Posture & body-language presence audit

**Skill**
- **CHESS** → Rated match benchmark *(e.g., 10-game rating avg)*
- **ITALIAN** → A1 assessment benchmark *(reading/speaking/comprehension)*
- **JIU-JITSU** → Belt rank or coached evaluation

---
#### 12) System Constraints (Mechanics Do Not Auto-Trigger)
- Stats are clamped to **0..100**
- Coins are **not implemented**
- Levels use **floored integer XP**
- Rulebook text does **not activate mechanics** without implemented logic
"""
        st.markdown(textwrap.dedent(rulebook_text).strip())
        st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

# ---------- SETTINGS ----------
with st.expander("⚙️ Settings", expanded=False):
    if st.button("Reset ALL", key="reset_all_btn_bottom"):
        reset_all()




