"""PMO/DMD Dashboard — Multirisk Three Days Impact-Based Forecast Bulletin.

Clean step-by-step workflow:
  Step 1: Review all agency inputs (TMA, MoW, GST, MoH, MoA, NEMC)
  Step 2: Build the DMD assessment (districts, recommendations, comments)
  Step 3: Generate & preview the bulletin

Includes: validation, copy-day, auto-import, templates, audit logging.
"""

import json
import io
import contextlib
from datetime import date, time, timedelta, datetime
from pathlib import Path

import streamlit as st

from .config import (
    DMD_OUTPUT_DIR, TMA_OUTPUT_DIR, DOCUMENTS_DIR, OUTPUT_DIR,
    DEFAULT_COLORS, DEFAULT_TEXTS, get_raw_region_name,
)
from .common_widgets import (
    alert_level_select, likelihood_impact_row,
    alert_color_pickers, district_selector_by_tier,
    dynamic_text_list,
)
from .map_widget import render_district_tier_map_selector
from .pdf_viewer import render_pdf_preview, render_side_by_side, get_pdf_pages
from .validation import validate_dmd_form, render_validation_results
from .templates import render_template_controls, auto_save, offer_restore
from .data_bridge import (
    tma_to_dmd_prefill, apply_prefill_to_session,
    load_latest_tma, auto_import_tma_if_available,
    get_bridge_timestamp,
    load_latest_mow, auto_import_mow_if_available,
    get_mow_bridge_timestamp, mow_to_dmd_prefill,
    apply_mow_prefill_to_session,
)
from .config import (
    get_districts_by_region, _clean_region_name,
    CATCHMENT_BASINS, ALERT_LEVELS as _ALL_ALERT_LEVELS,
)
from .tcvmp_bridge import is_tcvmp_available, get_facility_points
from .tcvmp_analysis import render_tcvmp_page


# ── Styling constants ─────────────────────────────────────────────
_ALERT_STYLE = {
    "ADVISORY": ("#FFFF00", "#000"),
    "WARNING": ("#FFA500", "#FFF"),
    "MAJOR_WARNING": ("#FF0000", "#FFF"),
}
_ALERT_LABEL = {
    "ADVISORY": "Advisory",
    "WARNING": "Warning",
    "MAJOR_WARNING": "Major Warning",
}
_ALERT_RANK = {"ADVISORY": 0, "WARNING": 1, "MAJOR_WARNING": 2}

def _step_header(num: int, title: str, desc: str):
    """Render a flat step header."""
    st.markdown(
        f'<div style="background:#f5f5f5;padding:10px 14px;border-left:3px solid #333;'
        f'margin-bottom:8px;">'
        f'<span style="font-family:monospace;font-size:0.78rem;color:#888;">'
        f'STEP {num}</span>'
        f'<div style="font-size:0.95rem;font-weight:600;color:#1a1a1a;">{title}</div>'
        f'<div style="font-size:0.8rem;color:#666;">{desc}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _agency_pill(name: str, available: bool, ts: str = ""):
    """Render a flat agency status indicator."""
    if available:
        ts_str = ""
        if ts:
            try:
                ts_str = " " + datetime.fromisoformat(ts).strftime("%H:%M")
            except ValueError:
                pass
        return (
            f'<span style="background:#e8e8e8;padding:3px 10px;border:1px solid #bbb;'
            f'font-size:0.78rem;font-family:monospace;display:inline-block;margin:2px;">'
            f'{name}{ts_str}</span>'
        )
    return (
        f'<span style="background:#f5f5f5;padding:3px 10px;border:1px solid #ddd;'
        f'font-size:0.78rem;font-family:monospace;color:#bbb;display:inline-block;margin:2px;">'
        f'{name} --</span>'
    )


# ══════════════════════════════════════════════════════════════════
# JSON builder
# ══════════════════════════════════════════════════════════════════

def _build_json(form: dict) -> dict:
    """Build Multirisk JSON from collected form data."""
    issue_date = form["issue_date"]
    issue_time = form["issue_time"]

    days = []
    for d in range(3):
        forecast_date = issue_date + timedelta(days=d)
        tiers = form.get(f"day{d}_tiers", {})

        day_data = {
            "day_number": d + 1,
            "date": forecast_date.strftime("%Y-%m-%d"),
            "hazard_panels": [
                {"type": "HEAVY_RAIN", "map_image": None},
                {"type": "LARGE_WAVES", "map_image": None},
                {"type": "STRONG_WIND", "map_image": None},
                {"type": "FLOODS", "map_image": None},
            ],
            "summary_map": None,
            "alert_tiers": {},
            "comments": {},
        }

        for tier_key in ["major_warning", "warning", "advisory"]:
            if tiers.get(tier_key):
                day_data["alert_tiers"][tier_key] = {
                    "text": None, "recommendations": [],
                }
            else:
                day_data["alert_tiers"][tier_key] = None

        recs = form.get(f"day{d}_recommendations", [])
        if recs:
            day_data["recommendations"] = recs
        rec_intro = form.get(f"day{d}_rec_intro", "")
        if rec_intro:
            day_data["recommendation_intro"] = rec_intro
        committee = form.get(f"day{d}_committee", "")
        if committee:
            day_data["committee_note"] = committee

        tma_entries = form.get(f"day{d}_tma_entries", [])
        if tma_entries:
            day_data["comments"]["tma"] = {"entries": tma_entries}
        mow_entries = form.get(f"day{d}_mow_entries", [])
        if mow_entries:
            day_data["comments"]["mow"] = {"entries": mow_entries}
        dmd = form.get(f"day{d}_dmd", {})
        if dmd.get("header") or dmd.get("bullets"):
            day_data["comments"]["dmd"] = dmd

        days.append(day_data)

    district_summaries = []
    for d in range(3):
        tiers = form.get(f"day{d}_tiers", {})
        district_summaries.append({
            "day_number": d + 1,
            "major_warning": tiers.get("major_warning", []),
            "warning": tiers.get("warning", []),
            "advisory": tiers.get("advisory", []),
        })

    return {
        "bulletin_number": form.get("bulletin_number", 1),
        "issue_date": issue_date.strftime("%Y-%m-%d"),
        "issue_time": issue_time.strftime("%H:%M"),
        "language": form.get("language", "sw"),
        "header_variant": form.get("header_variant", "new"),
        "days": days,
        "district_summaries": district_summaries,
    }


def _run_generation(json_data: dict) -> dict:
    """Run the Multirisk generation pipeline."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.pipeline import generate_multirisk

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_path = OUTPUT_DIR / f"_dmd_input_{timestamp}.json"
    tmp_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False))

    log_buf = io.StringIO()
    start = datetime.now()
    try:
        with contextlib.redirect_stdout(log_buf):
            result = generate_multirisk(
                input_path=str(tmp_path),
                output_dir=str(DMD_OUTPUT_DIR),
                output_format="both",
                auto_maps=True,
            )
        duration = (datetime.now() - start).total_seconds()
        return {"result": result, "logs": log_buf.getvalue(),
                "error": None, "duration": duration}
    except Exception as e:
        import traceback
        duration = (datetime.now() - start).total_seconds()
        return {"result": None, "logs": log_buf.getvalue(),
                "error": traceback.format_exc(), "duration": duration}
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# ══════════════════════════════════════════════════════════════════
# Day copy / defaults helpers
# ══════════════════════════════════════════════════════════════════

def _copy_dmd_day_data(source_day: int, target_day: int):
    """Copy all DMD form data from source day to target day."""
    src = f"dmd_d{source_day}"
    tgt = f"dmd_d{target_day}"

    for tier_key in ["major_warning", "warning", "advisory"]:
        src_key = f"{src}_tier_{tier_key}"
        tgt_key = f"{tgt}_tier_{tier_key}"
        if src_key in st.session_state:
            st.session_state[tgt_key] = list(st.session_state[src_key])

    for suffix in ["_rec_intro", "_committee"]:
        src_key = f"{src}{suffix}"
        tgt_key = f"{tgt}{suffix}"
        if src_key in st.session_state:
            st.session_state[tgt_key] = st.session_state[src_key]

    src_count = st.session_state.get(f"{src}_recs_count", 1)
    st.session_state[f"{tgt}_recs_count"] = src_count
    for i in range(src_count):
        src_key = f"{src}_recs_{i}"
        tgt_key = f"{tgt}_recs_{i}"
        if src_key in st.session_state:
            st.session_state[tgt_key] = st.session_state[src_key]

    for agency in ["tma", "mow"]:
        src_count = st.session_state.get(f"{src}_{agency}_count", 1)
        st.session_state[f"{tgt}_{agency}_count"] = src_count
        for t in range(src_count):
            for suffix in [f"_{agency}{t}_alert", f"_{agency}{t}_desc",
                          f"_{agency}{t}_rat_lik", f"_{agency}{t}_rat_imp"]:
                src_key = f"{src}{suffix}"
                tgt_key = f"{tgt}{suffix}"
                if src_key in st.session_state:
                    st.session_state[tgt_key] = st.session_state[src_key]

    for suffix in ["_dmd_header", "_dmd_rat_lik", "_dmd_rat_imp"]:
        src_key = f"{src}{suffix}"
        tgt_key = f"{tgt}{suffix}"
        if src_key in st.session_state:
            st.session_state[tgt_key] = st.session_state[src_key]

    src_count = st.session_state.get(f"{src}_dmd_bul_count", 1)
    st.session_state[f"{tgt}_dmd_bul_count"] = src_count
    for i in range(src_count):
        src_key = f"{src}_dmd_bul_{i}"
        tgt_key = f"{tgt}_dmd_bul_{i}"
        if src_key in st.session_state:
            st.session_state[tgt_key] = st.session_state[src_key]


def _load_defaults(day_idx: int, language: str):
    """Load default recommendation and DMD texts for a day."""
    prefix = f"dmd_d{day_idx}"
    texts = DEFAULT_TEXTS.get(language, DEFAULT_TEXTS["sw"])

    st.session_state[f"{prefix}_rec_intro"] = texts["recommendation_intro"]
    st.session_state[f"{prefix}_committee"] = texts["committee_note"]

    recs = texts["recommendations"]
    st.session_state[f"{prefix}_recs_count"] = len(recs)
    for i, r in enumerate(recs):
        st.session_state[f"{prefix}_recs_{i}"] = r

    st.session_state[f"{prefix}_dmd_header"] = texts["dmd_header"]
    bullets = texts["dmd_bullets"]
    st.session_state[f"{prefix}_dmd_bul_count"] = len(bullets)
    for i, b in enumerate(bullets):
        st.session_state[f"{prefix}_dmd_bul_{i}"] = b


# ══════════════════════════════════════════════════════════════════
# STEP 1: Agency Feed
# ══════════════════════════════════════════════════════════════════

def _render_agency_feed(issue_date: date):
    """Consolidated view of all agency data feeding into DMD."""
    tma_data = load_latest_tma()
    mow_data = load_latest_mow()
    gst_data = st.session_state.get("gst_latest_data")
    moh_data = st.session_state.get("moh_latest_data")
    moa_data = st.session_state.get("moa_latest_data")
    nemc_data = st.session_state.get("nemc_latest_data")
    tcvmp_ok = is_tcvmp_available()

    has_tma = bool(tma_data and tma_data.get("days"))
    has_mow = bool(mow_data and mow_data.get("days"))
    has_gst = bool(gst_data and gst_data.get("events"))
    has_moh = bool(moh_data and moh_data.get("outbreaks"))
    has_moa = bool(moa_data and moa_data.get("assessments"))
    has_nemc = bool(nemc_data and nemc_data.get("events"))

    # Agency status bar
    pills = []
    pills.append(_agency_pill("TMA", has_tma, get_bridge_timestamp() or ""))
    pills.append(_agency_pill("MoW", has_mow, get_mow_bridge_timestamp() or ""))
    pills.append(_agency_pill("GST", has_gst))
    pills.append(_agency_pill("MoH", has_moh))
    pills.append(_agency_pill("MoA", has_moa))
    pills.append(_agency_pill("NEMC", has_nemc))
    pills.append(_agency_pill("TCVMP", tcvmp_ok))

    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;">'
        + "".join(pills) + '</div>',
        unsafe_allow_html=True,
    )

    if not any([has_tma, has_mow, has_gst, has_moh, has_moa, has_nemc]):
        st.info("No agency data available yet. Agencies need to submit their assessments first.")
        return

    # Agency detail tabs
    agency_tabs = []
    agency_names = []
    if has_tma:
        agency_names.append("TMA")
    if has_mow:
        agency_names.append("MoW")
    if has_gst:
        agency_names.append("GST")
    if has_moh:
        agency_names.append("MoH")
    if has_moa:
        agency_names.append("MoA")
    if has_nemc:
        agency_names.append("NEMC")
    if tcvmp_ok:
        agency_names.append("TCVMP")

    agency_tabs = st.tabs(agency_names)
    tab_idx = 0

    # --- TMA Tab ---
    if has_tma:
        with agency_tabs[tab_idx]:
            _render_tma_feed(tma_data, issue_date)
        tab_idx += 1

    # --- MoW Tab ---
    if has_mow:
        with agency_tabs[tab_idx]:
            _render_mow_feed(mow_data, issue_date)
        tab_idx += 1

    # --- GST Tab ---
    if has_gst:
        with agency_tabs[tab_idx]:
            _render_generic_feed("GST", "Geological Events", gst_data.get("events", []),
                                 "#795548", _gst_card)
        tab_idx += 1

    # --- MoH Tab ---
    if has_moh:
        with agency_tabs[tab_idx]:
            _render_generic_feed("MoH", "Disease Outbreaks", moh_data.get("outbreaks", []),
                                 "#E91E63", _moh_card)
        tab_idx += 1

    # --- MoA Tab ---
    if has_moa:
        with agency_tabs[tab_idx]:
            _render_generic_feed("MoA", "Drought Assessments", moa_data.get("assessments", []),
                                 "#FF9800", _moa_card)
        tab_idx += 1

    # --- NEMC Tab ---
    if has_nemc:
        with agency_tabs[tab_idx]:
            _render_generic_feed("NEMC", "Air Quality Events", nemc_data.get("events", []),
                                 "#607D8B", _nemc_card)
        tab_idx += 1

    # --- TCVMP Tab ---
    if tcvmp_ok:
        with agency_tabs[tab_idx]:
            render_tcvmp_page(issue_date)
        tab_idx += 1


def _render_tma_feed(tma_data: dict, issue_date: date):
    """Render TMA hazard data in clean cards."""
    _hazard_label = {
        "HEAVY_RAIN": "Heavy Rain", "LARGE_WAVES": "Large Waves",
        "STRONG_WIND": "Strong Wind", "FLOODS": "Floods",
        "LANDSLIDES": "Landslides", "EXTREME_TEMPERATURE": "Extreme Temp.",
    }
    by_region = get_districts_by_region()
    days = tma_data.get("days", [])

    day_labels = [
        f"Day {d+1} ({(issue_date + timedelta(days=d)).strftime('%a %d/%m')})"
        for d in range(min(len(days), 5))
    ]
    day_tabs = st.tabs(day_labels) if len(day_labels) > 1 else [st.container()]

    for d_idx, dtab in enumerate(day_tabs):
        with dtab:
            if d_idx >= len(days):
                continue
            hazards = days[d_idx].get("hazards", [])
            if not hazards:
                st.caption("No warnings for this day.")
                continue

            for h in hazards:
                alert = h.get("alert_level", "ADVISORY")
                bg, tc = _ALERT_STYLE.get(alert, ("#EEE", "#000"))
                htype = _hazard_label.get(h.get("type", ""), h.get("type", ""))
                regions = h.get("regions", [])
                n_dist = sum(len(by_region.get(_clean_region_name(r), [])) for r in regions)

                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(
                            f'<span style="background:{bg};color:{tc};padding:2px 10px;'
                            f'border-radius:4px;font-size:12px;font-weight:700;">'
                            f'{_ALERT_LABEL.get(alert, alert)}</span> '
                            f'<b>{htype}</b>',
                            unsafe_allow_html=True,
                        )
                        if h.get("description"):
                            st.caption(h["description"])
                    with c2:
                        st.markdown(
                            f'<div style="text-align:right;font-size:12px;color:#666;">'
                            f'{len(regions)} regions<br>{n_dist} districts</div>',
                            unsafe_allow_html=True,
                        )


def _render_mow_feed(mow_data: dict, issue_date: date):
    """Render MoW flood risk data in clean cards."""
    days = mow_data.get("days", [])

    day_labels = [
        f"Day {d+1} ({(issue_date + timedelta(days=d)).strftime('%a %d/%m')})"
        for d in range(min(len(days), 3))
    ]
    day_tabs = st.tabs(day_labels) if len(day_labels) > 1 else [st.container()]

    for d_idx, dtab in enumerate(day_tabs):
        with dtab:
            if d_idx >= len(days):
                continue
            assessments = days[d_idx].get("assessments", [])
            if not assessments:
                st.caption("No flood risk assessments for this day.")
                continue

            for a in assessments:
                alert = a.get("alert_level", "ADVISORY")
                bg, tc = _ALERT_STYLE.get(alert, ("#EEE", "#000"))
                basins = a.get("basins", [])
                districts = a.get("districts", [])
                basin_text = ", ".join(
                    CATCHMENT_BASINS.get(b, {}).get("label", b) for b in basins
                ) or "Flood Risk"

                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(
                            f'<span style="background:{bg};color:{tc};padding:2px 10px;'
                            f'border-radius:4px;font-size:12px;font-weight:700;">'
                            f'{_ALERT_LABEL.get(alert, alert)}</span> '
                            f'<b>{basin_text}</b>',
                            unsafe_allow_html=True,
                        )
                        if a.get("description"):
                            st.caption(a["description"])
                    with c2:
                        st.markdown(
                            f'<div style="text-align:right;font-size:12px;color:#666;">'
                            f'{len(districts)} districts</div>',
                            unsafe_allow_html=True,
                        )


def _gst_card(event: dict):
    """Render a single GST event card."""
    alert = event.get("alert_level", "ADVISORY")
    bg, tc = _ALERT_STYLE.get(alert, ("#EEE", "#000"))
    etype = event.get("type", "EARTHQUAKE")
    label_map = {"EARTHQUAKE": "Earthquake", "LANDSLIDES": "Landslide", "VOLCANO": "Volcano"}

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(
                f'<span style="background:{bg};color:{tc};padding:2px 10px;'
                f'border-radius:4px;font-size:12px;font-weight:700;">'
                f'{_ALERT_LABEL.get(alert, alert)}</span> '
                f'<b>{label_map.get(etype, etype)}</b>',
                unsafe_allow_html=True,
            )
            if etype == "EARTHQUAKE" and event.get("magnitude"):
                st.caption(f"Magnitude: {event['magnitude']} | Depth: {event.get('depth_km', '—')} km")
            elif etype == "VOLCANO" and event.get("activity_type"):
                st.caption(f"Activity: {event['activity_type']} | VHI: {event.get('volcanic_hazard_index', '—')}")
            if event.get("description"):
                st.caption(event["description"])
        with c2:
            r = len(event.get("regions", []))
            d = len(event.get("districts", []))
            st.markdown(
                f'<div style="text-align:right;font-size:12px;color:#666;">'
                f'{r} regions<br>{d} districts</div>',
                unsafe_allow_html=True,
            )


def _moh_card(event: dict):
    """Render a single MoH outbreak card."""
    alert = event.get("alert_level", "ADVISORY")
    bg, tc = _ALERT_STYLE.get(alert, ("#EEE", "#000"))

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(
                f'<span style="background:{bg};color:{tc};padding:2px 10px;'
                f'border-radius:4px;font-size:12px;font-weight:700;">'
                f'{_ALERT_LABEL.get(alert, alert)}</span> '
                f'<b>{event.get("disease", "Disease Outbreak")}</b>',
                unsafe_allow_html=True,
            )
            parts = []
            if event.get("confirmed_cases"):
                parts.append(f"Cases: {event['confirmed_cases']}")
            if event.get("deaths"):
                parts.append(f"Deaths: {event['deaths']}")
            if event.get("trend"):
                parts.append(f"Trend: {event['trend']}")
            if parts:
                st.caption(" | ".join(parts))
            if event.get("description"):
                st.caption(event["description"])
        with c2:
            r = len(event.get("regions", []))
            d = len(event.get("districts", []))
            st.markdown(
                f'<div style="text-align:right;font-size:12px;color:#666;">'
                f'{r} regions<br>{d} districts</div>',
                unsafe_allow_html=True,
            )


def _moa_card(event: dict):
    """Render a single MoA drought card."""
    alert = event.get("alert_level", "ADVISORY")
    bg, tc = _ALERT_STYLE.get(alert, ("#EEE", "#000"))

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(
                f'<span style="background:{bg};color:{tc};padding:2px 10px;'
                f'border-radius:4px;font-size:12px;font-weight:700;">'
                f'{_ALERT_LABEL.get(alert, alert)}</span> '
                f'<b>{event.get("severity", "Drought")}</b>',
                unsafe_allow_html=True,
            )
            parts = []
            if event.get("rainfall_pct_normal"):
                parts.append(f"Rainfall: {event['rainfall_pct_normal']}% of normal")
            if event.get("vegetation_ndvi"):
                parts.append(f"NDVI: {event['vegetation_ndvi']}")
            if parts:
                st.caption(" | ".join(parts))
            if event.get("description"):
                st.caption(event["description"])
        with c2:
            r = len(event.get("regions", []))
            d = len(event.get("districts", []))
            st.markdown(
                f'<div style="text-align:right;font-size:12px;color:#666;">'
                f'{r} regions<br>{d} districts</div>',
                unsafe_allow_html=True,
            )


def _nemc_card(event: dict):
    """Render a single NEMC air pollution card."""
    alert = event.get("alert_level", "ADVISORY")
    bg, tc = _ALERT_STYLE.get(alert, ("#EEE", "#000"))

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(
                f'<span style="background:{bg};color:{tc};padding:2px 10px;'
                f'border-radius:4px;font-size:12px;font-weight:700;">'
                f'{_ALERT_LABEL.get(alert, alert)}</span> '
                f'<b>Air Pollution — {event.get("source", "Unknown")}</b>',
                unsafe_allow_html=True,
            )
            parts = []
            if event.get("aqi_value"):
                parts.append(f"AQI: {event['aqi_value']}")
            if event.get("pollutants"):
                parts.append(f"Pollutants: {', '.join(event['pollutants'])}")
            if parts:
                st.caption(" | ".join(parts))
            if event.get("description"):
                st.caption(event["description"])
        with c2:
            r = len(event.get("regions", []))
            d = len(event.get("districts", []))
            st.markdown(
                f'<div style="text-align:right;font-size:12px;color:#666;">'
                f'{r} regions<br>{d} districts</div>',
                unsafe_allow_html=True,
            )


def _render_generic_feed(agency: str, title: str, items: list,
                         _color: str, card_fn):
    """Render a list of agency events using a card function."""
    st.markdown(f"**{title}** ({len(items)})")
    if not items:
        st.caption(f"No {title.lower()} reported.")
        return
    for item in items:
        card_fn(item)


# ══════════════════════════════════════════════════════════════════
# STEP 2: Agency Comments
# ══════════════════════════════════════════════════════════════════

def _collect_agency_comments(day_idx: int, form: dict):
    """Collect TMA, MoW, and DMD comments for a day."""
    prefix = f"dmd_d{day_idx}"

    # --- TMA Comments ---
    with st.expander("TMA Comments", expanded=False):
        tma_count_key = f"{prefix}_tma_count"
        if tma_count_key not in st.session_state:
            st.session_state[tma_count_key] = 1

        tma_entries = []
        for t in range(st.session_state[tma_count_key]):
            if t > 0:
                st.markdown("---")
            tcol1, tcol2 = st.columns([1, 3])
            with tcol1:
                alert = alert_level_select("Level", key=f"{prefix}_tma{t}_alert",
                                           include_no_warning=False)
            with tcol2:
                desc = st.text_area(
                    "Description", key=f"{prefix}_tma{t}_desc", height=68,
                    placeholder="ANGALIZO la mvua kubwa limetolewa...",
                )
            lik, imp = likelihood_impact_row(key_prefix=f"{prefix}_tma{t}_rat")

            if desc:
                tma_entries.append({"alert_level": alert, "description": desc,
                                    "likelihood": lik, "impact": imp})

        c1, c2 = st.columns(2)
        with c1:
            if st.button("+ Add", key=f"{prefix}_add_tma", use_container_width=True):
                st.session_state[tma_count_key] += 1
                st.rerun()
        with c2:
            if st.session_state[tma_count_key] > 1:
                if st.button("- Remove", key=f"{prefix}_rem_tma", use_container_width=True):
                    st.session_state[tma_count_key] -= 1
                    st.rerun()

        form[f"day{day_idx}_tma_entries"] = tma_entries

    # --- MoW Comments ---
    with st.expander("MoW Comments", expanded=False):
        mow_count_key = f"{prefix}_mow_count"
        if mow_count_key not in st.session_state:
            st.session_state[mow_count_key] = 1

        mow_entries = []
        for m in range(st.session_state[mow_count_key]):
            if m > 0:
                st.markdown("---")
            mcol1, mcol2 = st.columns([1, 3])
            with mcol1:
                alert = alert_level_select("Level", key=f"{prefix}_mow{m}_alert",
                                           include_no_warning=False)
            with mcol2:
                desc = st.text_area(
                    "Description", key=f"{prefix}_mow{m}_desc", height=68,
                    placeholder="ANGALIZO la ongezeko la maji...",
                )
            lik, imp = likelihood_impact_row(key_prefix=f"{prefix}_mow{m}_rat")

            if desc:
                mow_entries.append({"alert_level": alert, "description": desc,
                                    "likelihood": lik, "impact": imp})

        c1, c2 = st.columns(2)
        with c1:
            if st.button("+ Add", key=f"{prefix}_add_mow", use_container_width=True):
                st.session_state[mow_count_key] += 1
                st.rerun()
        with c2:
            if st.session_state[mow_count_key] > 1:
                if st.button("- Remove", key=f"{prefix}_rem_mow", use_container_width=True):
                    st.session_state[mow_count_key] -= 1
                    st.rerun()

        form[f"day{day_idx}_mow_entries"] = mow_entries

    # --- DMD Impact Assessment ---
    with st.expander("DMD Impact Assessment", expanded=False):
        dmd_header = st.text_input(
            "Header", key=f"{prefix}_dmd_header",
            placeholder="Madhara yanayoweza kutokea:",
        )
        dmd_bullets = dynamic_text_list(
            "Impact Bullets", key_prefix=f"{prefix}_dmd_bul",
            placeholder="Makazi kuzingirwa na maji.",
        )
        dmd_lik, dmd_imp = likelihood_impact_row(key_prefix=f"{prefix}_dmd_rat")

        dmd_data = {}
        if dmd_header:
            dmd_data["header"] = dmd_header
        if dmd_bullets:
            dmd_data["bullets"] = dmd_bullets
        if dmd_lik:
            dmd_data["likelihood"] = dmd_lik
        if dmd_imp:
            dmd_data["impact"] = dmd_imp
        form[f"day{day_idx}_dmd"] = dmd_data


# ══════════════════════════════════════════════════════════════════
# Error display
# ══════════════════════════════════════════════════════════════════

def _render_error(gen_result: dict):
    st.error("Generation failed!")
    error_text = gen_result["error"]

    if "LibreOffice" in error_text or "libreoffice" in error_text:
        st.warning("PDF conversion requires LibreOffice. Install: `sudo apt install libreoffice`")
    elif "ValidationError" in error_text or "ValueError" in error_text:
        st.warning("Input data validation failed. Check all required fields.")

    with st.expander("Technical Details", expanded=False):
        st.code(error_text, language="text")


# ══════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════

def render_dmd_page():
    """Render the PMO/DMD Multirisk dashboard — clean 3-step workflow."""
    username = st.session_state.get("current_username", "unknown")

    offer_restore(username, "dmd", "dmd")
    render_template_controls("dmd", "dmd")

    # Auto-import agency data
    tma_imported = auto_import_tma_if_available()
    mow_imported = auto_import_mow_if_available()
    if tma_imported or mow_imported:
        sources = []
        if tma_imported:
            sources.append("TMA")
        if mow_imported:
            sources.append("MoW")
        st.success(f"New {' & '.join(sources)} data imported and pre-filled.")

    # ── Bulletin Metadata ─────────────────────────────────────────
    with st.container(border=True):
        mc = st.columns([1, 1, 1, 1.5, 1.5])
        with mc[0]:
            bulletin_num = st.number_input("Bulletin #", min_value=1, value=122,
                                           key="dmd_bnum")
        with mc[1]:
            language = st.selectbox("Language", ["sw", "en"], index=0, key="dmd_lang")
        with mc[2]:
            header_var = st.selectbox("Header", ["new", "old"], index=0, key="dmd_header")
        with mc[3]:
            issue_date = st.date_input("Issue Date", value=date.today(), key="dmd_date")
        with mc[4]:
            issue_time = st.time_input("Issue Time", value=time(9, 42), key="dmd_time")

    form = {
        "bulletin_number": bulletin_num,
        "language": language,
        "header_variant": header_var,
        "issue_date": issue_date,
        "issue_time": issue_time,
    }

    # Color customization (sidebar)
    with st.sidebar:
        with st.expander("Customize Colors", expanded=False):
            custom_colors = alert_color_pickers("dmd_colors")

    # ══════════════════════════════════════════════════════════════
    # STEP 1: Review Agency Inputs
    # ══════════════════════════════════════════════════════════════
    _step_header(1, "Review Agency Inputs",
                 "Review data from TMA, MoW, GST, MoH, MoA, NEMC before building your assessment.")

    with st.expander("Agency Data Feed", expanded=True):
        _render_agency_feed(issue_date)

    # Re-import controls
    with st.expander("Re-import / Refresh Agency Data", expanded=False):
        rc = st.columns(3)
        with rc[0]:
            tma_data = load_latest_tma()
            if tma_data:
                if st.button("Re-import TMA", key="dmd_reimport_tma", use_container_width=True):
                    prefill = tma_to_dmd_prefill(tma_data)
                    apply_prefill_to_session(prefill)
                    st.session_state["_dmd_last_import_ts"] = get_bridge_timestamp()
                    st.success("TMA data re-imported!")
                    st.rerun()
        with rc[1]:
            mow_data = load_latest_mow()
            if mow_data:
                if st.button("Re-import MoW", key="dmd_reimport_mow", use_container_width=True):
                    prefill = mow_to_dmd_prefill(mow_data)
                    apply_mow_prefill_to_session(prefill)
                    st.session_state["_dmd_last_mow_import_ts"] = get_mow_bridge_timestamp()
                    st.success("MoW data re-imported!")
                    st.rerun()
        with rc[2]:
            pdfs = sorted(TMA_OUTPUT_DIR.glob("*.pdf"))
            if pdfs:
                with st.popover("View TMA Products"):
                    for pdf in pdfs[-3:]:
                        with open(pdf, "rb") as f:
                            st.download_button(pdf.name, f.read(), pdf.name,
                                               "application/pdf", key=f"tma_dl_{pdf.stem}")

    # ══════════════════════════════════════════════════════════════
    # STEP 2: Build DMD Assessment
    # ══════════════════════════════════════════════════════════════
    st.markdown("---")
    _step_header(2, "Build DMD Assessment",
                 "Select districts per alert tier, add recommendations, and agency comments.")

    day_labels = [
        f"Day {d+1} ({(issue_date + timedelta(days=d)).strftime('%a %d/%m')})"
        for d in range(3)
    ]
    tabs = st.tabs(day_labels)

    for d, tab in enumerate(tabs):
        with tab:
            # Toolbar
            tc = st.columns([2, 2, 2])
            with tc[0]:
                if d > 0:
                    copy_src = st.selectbox(
                        "Copy from", [f"Day {i+1}" for i in range(d)],
                        key=f"dmd_copy_src_{d}",
                    )
                    if st.button("Copy", key=f"dmd_copy_btn_{d}", use_container_width=True):
                        _copy_dmd_day_data(int(copy_src.split()[-1]) - 1, d)
                        st.rerun()
            with tc[2]:
                if st.button("Load Defaults", key=f"dmd_d{d}_fill_defaults",
                             use_container_width=True):
                    _load_defaults(d, language)
                    st.rerun()

            # ── District Alert Tiers ──
            st.markdown("##### District Alert Tiers")
            tier_keys = {
                "advisory": f"dmd_d{d}_tier_advisory",
                "warning": f"dmd_d{d}_tier_warning",
                "major_warning": f"dmd_d{d}_tier_major_warning",
            }
            tier_colors = {
                "advisory": custom_colors.get("ADVISORY", "#FFFF00"),
                "warning": custom_colors.get("WARNING", "#FFA500"),
                "major_warning": custom_colors.get("MAJOR_WARNING", "#FF0000"),
            }
            render_district_tier_map_selector(
                key_prefix=f"dmd_d{d}_tmap",
                tier_keys=tier_keys,
                tier_colors=tier_colors,
            )
            tiers = district_selector_by_tier(key_prefix=f"dmd_d{d}_tier")
            form[f"day{d}_tiers"] = tiers

            st.markdown("---")

            # ── Recommendations ──
            st.markdown("##### Recommendations")
            rec_intro = st.text_input(
                "Introduction", key=f"dmd_d{d}_rec_intro",
                placeholder="Jamii inasisitizwa kuchukua hatua za tahadhari ikijumuisha:",
            )
            form[f"day{d}_rec_intro"] = rec_intro

            recs = dynamic_text_list(
                "Bullets", key_prefix=f"dmd_d{d}_recs",
                placeholder="Wavuvi na watumiaji wa bahari...",
            )
            form[f"day{d}_recommendations"] = recs

            committee = st.text_area(
                "Committee Note", key=f"dmd_d{d}_committee", height=68,
                placeholder="Kamati za Usimamizi wa Maafa...",
            )
            form[f"day{d}_committee"] = committee

            st.markdown("---")

            # ── Agency Comments ──
            st.markdown("##### Agency Comments")
            _collect_agency_comments(d, form)

    # ══════════════════════════════════════════════════════════════
    # STEP 3: Generate Bulletin
    # ══════════════════════════════════════════════════════════════
    st.markdown("---")
    _step_header(3, "Generate Bulletin",
                 "Validate and generate the Multirisk Impact-Based Forecast Bulletin.")

    if st.button("Generate Multirisk Bulletin", type="primary",
                 use_container_width=True, key="dmd_generate"):
        validation = validate_dmd_form(form)
        if not render_validation_results(validation):
            st.stop()

        json_data = _build_json(form)

        progress = st.progress(0, text="Preparing...")
        progress.progress(10, text="Generating 15 maps...")

        gen_result = _run_generation(json_data)
        st.session_state["dmd_gen_result"] = gen_result

        progress.progress(100, text="Complete!")

        auto_save(username, "dmd", "dmd")

        from .audit import log_generation
        log_generation(
            username, st.session_state.get("current_role", "unknown"),
            "multirisk", json_data, gen_result, gen_result["duration"],
        )

    # ── Results ──
    gen_result = st.session_state.get("dmd_gen_result")
    if not gen_result:
        return

    st.markdown("---")

    if gen_result["error"]:
        _render_error(gen_result)
        return

    result = gen_result.get("result", {})
    pdf_path = result.get("pdf")
    docx_path = result.get("docx")

    st.success("Bulletin generated successfully!")

    mc = st.columns(4)
    with mc[0]:
        st.metric("Time", f"{gen_result['duration']:.1f}s")
    with mc[1]:
        if pdf_path and Path(pdf_path).exists():
            st.metric("Pages", len(get_pdf_pages(pdf_path)))
    with mc[2]:
        if pdf_path and Path(pdf_path).exists():
            st.metric("PDF", f"{Path(pdf_path).stat().st_size / 1024:.0f} KB")
    with mc[3]:
        if docx_path and Path(docx_path).exists():
            st.metric("DOCX", f"{Path(docx_path).stat().st_size / 1024:.0f} KB")

    with st.expander("Generation Log", expanded=False):
        st.code(gen_result.get("logs", ""), language="text")

    if not pdf_path or not Path(pdf_path).exists():
        return

    tab_preview, tab_compare, tab_download = st.tabs([
        "Preview", "Compare with Reference", "Download",
    ])
    with tab_preview:
        render_pdf_preview(pdf_path, "Generated Bulletin", key_prefix="dmd_preview")
    with tab_compare:
        refs = sorted(DOCUMENTS_DIR.glob("Tanzania_Multirisk*.pdf"))
        if refs:
            ref_names = [r.name for r in refs]
            selected = st.selectbox("Reference", ref_names,
                                    index=len(ref_names) - 1, key="dmd_ref_sel")
            render_side_by_side(pdf_path, str(DOCUMENTS_DIR / selected),
                                key_prefix="dmd_cmp")
        else:
            st.info("No reference PDFs in documents/")
    with tab_download:
        c1, c2 = st.columns(2)
        with c1:
            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    st.download_button("Download PDF", f.read(),
                                       Path(pdf_path).name, "application/pdf",
                                       use_container_width=True)
        with c2:
            if docx_path and Path(docx_path).exists():
                with open(docx_path, "rb") as f:
                    st.download_button("Download DOCX", f.read(),
                                       Path(docx_path).name,
                                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                       use_container_width=True)
