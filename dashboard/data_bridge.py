"""Data bridge: convert agency form data to DMD pre-fill data.

Handles TMA and MoW data bridges to PMO/DMD.
Maps TMA regions -> DMD districts using the geodata region->district mapping.
Maps MoW catchments -> DMD districts using basin->district mapping.
Maps alert levels -> DMD district tiers.
Carries agency descriptions as DMD comment entries.

Persists agency data to shared files so the DMD page can auto-import
even across sessions/users. Includes timestamps for change detection.
"""

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from .config import get_districts_by_region, _clean_region_name

# Shared files for agency -> DMD data exchange
_BRIDGE_DIR = Path(__file__).parent.parent / "output" / "bridge"
_BRIDGE_FILE = _BRIDGE_DIR / "latest_tma.json"
_MOW_BRIDGE_FILE = _BRIDGE_DIR / "latest_mow.json"


def save_tma_for_dmd(tma_json_data: dict):
    """Persist the latest TMA JSON so the DMD page can pick it up."""
    _BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    # Wrap with a timestamp so DMD can detect newer data
    envelope = {
        "_bridge_ts": datetime.now().isoformat(),
        "data": tma_json_data,
    }
    _BRIDGE_FILE.write_text(json.dumps(envelope, default=str, indent=2))
    # Also keep in session state for same-session access
    st.session_state["tma_last_json"] = tma_json_data
    st.session_state["_tma_bridge_ts"] = envelope["_bridge_ts"]


def _load_envelope() -> dict | None:
    """Load the raw bridge envelope (with timestamp)."""
    if _BRIDGE_FILE.exists():
        try:
            return json.loads(_BRIDGE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def get_bridge_timestamp() -> str | None:
    """Get the timestamp of the latest TMA bridge data."""
    # Session state first (same session)
    ts = st.session_state.get("_tma_bridge_ts")
    if ts:
        return ts
    envelope = _load_envelope()
    if envelope:
        return envelope.get("_bridge_ts")
    return None


def load_latest_tma() -> dict | None:
    """Load the latest TMA JSON data (session state first, then file)."""
    # Prefer session state (same session)
    if st.session_state.get("tma_last_json"):
        return st.session_state["tma_last_json"]
    # Fall back to shared file (cross-session / cross-user)
    envelope = _load_envelope()
    if envelope:
        data = envelope.get("data", envelope)
        ts = envelope.get("_bridge_ts")
        st.session_state["tma_last_json"] = data
        if ts:
            st.session_state["_tma_bridge_ts"] = ts
        return data
    return None


def tma_to_dmd_prefill(tma_json_data: dict) -> dict:
    """Convert TMA JSON data into DMD form pre-fill data.

    Returns a dict with keys like 'day{d}_tiers', 'day{d}_tma_entries'.
    """
    by_region = get_districts_by_region()
    prefill = {}

    days = tma_json_data.get("days", [])
    for d_idx, day in enumerate(days):
        if d_idx >= 3:  # DMD only has 3 days
            break

        tiers = {"major_warning": [], "warning": [], "advisory": []}

        for hazard in day.get("hazards", []):
            alert = hazard.get("alert_level", "ADVISORY")
            regions = hazard.get("regions", [])

            # Map alert to tier
            if alert == "MAJOR_WARNING":
                tier_key = "major_warning"
            elif alert == "WARNING":
                tier_key = "warning"
            else:
                tier_key = "advisory"

            # Expand regions to districts
            for region_name in regions:
                display_name = _clean_region_name(region_name)
                districts = by_region.get(display_name, [])
                for dist in districts:
                    if dist not in tiers[tier_key]:
                        tiers[tier_key].append(dist)

        prefill[f"day{d_idx}_tiers"] = tiers

        # Carry TMA hazard descriptions as TMA entries in DMD
        tma_entries = []
        for hazard in day.get("hazards", []):
            if hazard.get("description"):
                tma_entries.append({
                    "alert_level": hazard.get("alert_level", "ADVISORY"),
                    "description": hazard.get("description", ""),
                    "likelihood": hazard.get("likelihood", "MEDIUM"),
                    "impact": hazard.get("impact", "MEDIUM"),
                })
        prefill[f"day{d_idx}_tma_entries"] = tma_entries

    return prefill


def apply_prefill_to_session(prefill: dict):
    """Apply pre-fill data to DMD session state keys."""
    for d in range(3):
        tiers = prefill.get(f"day{d}_tiers", {})
        for tier_key in ["major_warning", "warning", "advisory"]:
            session_key = f"dmd_d{d}_tier_{tier_key}"
            districts = sorted(tiers.get(tier_key, []))
            if districts:
                st.session_state[session_key] = districts

        # Pre-fill TMA entries (description + alert level + likelihood + impact)
        tma_entries = prefill.get(f"day{d}_tma_entries", [])
        if tma_entries:
            st.session_state[f"dmd_d{d}_tma_count"] = len(tma_entries)
            for t_idx, entry in enumerate(tma_entries):
                # Map alert level to selectbox index
                level_map = {"ADVISORY": 0, "WARNING": 1, "MAJOR_WARNING": 2}
                st.session_state[f"dmd_d{d}_tma{t_idx}_alert"] = level_map.get(
                    entry["alert_level"], 0
                )
                st.session_state[f"dmd_d{d}_tma{t_idx}_desc"] = entry.get("description", "")
                # Also carry likelihood and impact
                lik_map = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
                st.session_state[f"dmd_d{d}_tma{t_idx}_rat_lik"] = lik_map.get(
                    entry.get("likelihood", "MEDIUM"), 1
                )
                st.session_state[f"dmd_d{d}_tma{t_idx}_rat_imp"] = lik_map.get(
                    entry.get("impact", "MEDIUM"), 1
                )

    # Sync issue date/time from TMA if available
    tma_date = prefill.get("issue_date")
    tma_time = prefill.get("issue_time")
    if tma_date:
        st.session_state["dmd_date"] = tma_date
    if tma_time:
        st.session_state["dmd_time"] = tma_time


def _has_newer_tma_data() -> bool:
    """Check if TMA bridge has newer data than what DMD last imported."""
    current_ts = get_bridge_timestamp()
    if not current_ts:
        return False
    last_imported_ts = st.session_state.get("_dmd_last_import_ts")
    if not last_imported_ts:
        return True  # Never imported
    return current_ts > last_imported_ts


def auto_import_tma_if_available() -> bool:
    """Auto-import TMA data into DMD session if new data is available.

    Detects newer TMA data by comparing timestamps, so it re-imports
    whenever TMA generates a new bulletin (not just on first load).

    Returns True if data was imported, False otherwise.
    """
    if not _has_newer_tma_data():
        return False

    tma_data = load_latest_tma()
    if not tma_data:
        return False

    prefill = tma_to_dmd_prefill(tma_data)
    # Also carry issue date/time for DMD sync
    from datetime import date as date_type, time as time_type
    issue_date_str = tma_data.get("issue_date")
    issue_time_str = tma_data.get("issue_time")
    if issue_date_str:
        try:
            prefill["issue_date"] = date_type.fromisoformat(issue_date_str)
        except ValueError:
            pass
    if issue_time_str:
        try:
            parts = issue_time_str.split(":")
            prefill["issue_time"] = time_type(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass

    apply_prefill_to_session(prefill)
    st.session_state["_dmd_last_import_ts"] = get_bridge_timestamp()
    return True


# ═══════════════════════════════════════════════════════════════════
# MoW (Ministry of Water) Bridge
# ═══════════════════════════════════════════════════════════════════

def save_mow_for_dmd(mow_json_data: dict):
    """Persist the latest MoW JSON so the DMD page can pick it up."""
    _BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    envelope = {
        "_bridge_ts": datetime.now().isoformat(),
        "data": mow_json_data,
    }
    _MOW_BRIDGE_FILE.write_text(json.dumps(envelope, default=str, indent=2))
    st.session_state["mow_last_json"] = mow_json_data
    st.session_state["_mow_bridge_ts"] = envelope["_bridge_ts"]


def _load_mow_envelope() -> dict | None:
    """Load the raw MoW bridge envelope."""
    if _MOW_BRIDGE_FILE.exists():
        try:
            return json.loads(_MOW_BRIDGE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def get_mow_bridge_timestamp() -> str | None:
    """Get the timestamp of the latest MoW bridge data."""
    ts = st.session_state.get("_mow_bridge_ts")
    if ts:
        return ts
    envelope = _load_mow_envelope()
    if envelope:
        return envelope.get("_bridge_ts")
    return None


def load_latest_mow() -> dict | None:
    """Load the latest MoW JSON data (session state first, then file)."""
    if st.session_state.get("mow_last_json"):
        return st.session_state["mow_last_json"]
    envelope = _load_mow_envelope()
    if envelope:
        data = envelope.get("data", envelope)
        ts = envelope.get("_bridge_ts")
        st.session_state["mow_last_json"] = data
        if ts:
            st.session_state["_mow_bridge_ts"] = ts
        return data
    return None


def mow_to_dmd_prefill(mow_json_data: dict) -> dict:
    """Convert MoW JSON data into DMD form pre-fill data.

    MoW works with catchment basins, but the output maps to districts
    with alert tiers, same as TMA.
    """
    prefill = {}
    days = mow_json_data.get("days", [])

    for d_idx, day in enumerate(days):
        if d_idx >= 3:
            break

        tiers = {"major_warning": [], "warning": [], "advisory": []}

        for assessment in day.get("assessments", []):
            alert = assessment.get("alert_level", "ADVISORY")
            districts = assessment.get("districts", [])

            if alert == "MAJOR_WARNING":
                tier_key = "major_warning"
            elif alert == "WARNING":
                tier_key = "warning"
            else:
                tier_key = "advisory"

            for dist in districts:
                if dist not in tiers[tier_key]:
                    tiers[tier_key].append(dist)

        prefill[f"day{d_idx}_tiers"] = tiers

        # Carry MoW descriptions as MoW comment entries in DMD
        mow_entries = []
        for assessment in day.get("assessments", []):
            if assessment.get("description"):
                mow_entries.append({
                    "alert_level": assessment.get("alert_level", "ADVISORY"),
                    "description": assessment.get("description", ""),
                    "likelihood": assessment.get("likelihood", "MEDIUM"),
                    "impact": assessment.get("impact", "MEDIUM"),
                })
        prefill[f"day{d_idx}_mow_entries"] = mow_entries

    return prefill


def apply_mow_prefill_to_session(prefill: dict):
    """Apply MoW pre-fill data to DMD session state keys.

    MoW districts are MERGED with existing tier data (from TMA),
    taking the highest alert level when a district appears in both.
    """
    alert_rank = {"advisory": 0, "warning": 1, "major_warning": 2}

    for d in range(3):
        tiers = prefill.get(f"day{d}_tiers", {})
        for tier_key in ["major_warning", "warning", "advisory"]:
            session_key = f"dmd_d{d}_tier_{tier_key}"
            new_districts = tiers.get(tier_key, [])
            existing = list(st.session_state.get(session_key, []))

            for dist in new_districts:
                # Check if district already in a higher tier
                dominated = False
                for higher_tier in ["major_warning", "warning", "advisory"]:
                    if alert_rank.get(higher_tier, 0) > alert_rank.get(tier_key, 0):
                        higher_key = f"dmd_d{d}_tier_{higher_tier}"
                        if dist in st.session_state.get(higher_key, []):
                            dominated = True
                            break
                if not dominated and dist not in existing:
                    existing.append(dist)

            if existing:
                st.session_state[session_key] = sorted(existing)

        # Pre-fill MoW entries
        mow_entries = prefill.get(f"day{d}_mow_entries", [])
        if mow_entries:
            st.session_state[f"dmd_d{d}_mow_count"] = len(mow_entries)
            level_map = {"ADVISORY": 0, "WARNING": 1, "MAJOR_WARNING": 2}
            lik_map = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
            for m_idx, entry in enumerate(mow_entries):
                st.session_state[f"dmd_d{d}_mow{m_idx}_alert"] = level_map.get(
                    entry["alert_level"], 0
                )
                st.session_state[f"dmd_d{d}_mow{m_idx}_desc"] = entry.get("description", "")
                st.session_state[f"dmd_d{d}_mow{m_idx}_rat_lik"] = lik_map.get(
                    entry.get("likelihood", "MEDIUM"), 1
                )
                st.session_state[f"dmd_d{d}_mow{m_idx}_rat_imp"] = lik_map.get(
                    entry.get("impact", "MEDIUM"), 1
                )


def _has_newer_mow_data() -> bool:
    """Check if MoW bridge has newer data than what DMD last imported."""
    current_ts = get_mow_bridge_timestamp()
    if not current_ts:
        return False
    last_imported_ts = st.session_state.get("_dmd_last_mow_import_ts")
    if not last_imported_ts:
        return True
    return current_ts > last_imported_ts


def auto_import_mow_if_available() -> bool:
    """Auto-import MoW data into DMD session if new data is available."""
    if not _has_newer_mow_data():
        return False

    mow_data = load_latest_mow()
    if not mow_data:
        return False

    prefill = mow_to_dmd_prefill(mow_data)
    apply_mow_prefill_to_session(prefill)
    st.session_state["_dmd_last_mow_import_ts"] = get_mow_bridge_timestamp()
    return True
