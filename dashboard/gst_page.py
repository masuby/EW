"""GST Dashboard — Geological Survey of Tanzania.

Monitors: Earthquakes, Landslides, Volcanoes.
Region/district selection with map, alert levels, and data export
to PMO/DMD via session state.
"""

import json
from datetime import date, time, timedelta, datetime
from pathlib import Path

import streamlit as st

from .config import (
    GST_OUTPUT_DIR, OUTPUT_DIR,
    ALERT_LEVELS, LIKELIHOOD_LEVELS, IMPACT_LEVELS,
    GST_HAZARD_TYPES, GST_SEVERITY_LEVELS, DEFAULT_IMPACTS_NEW,
    get_region_names,
)
from .map_widget import render_map_selector
from .templates import render_template_controls, auto_save, offer_restore


ALERT_COLOR_MAP = {a["key"]: a["color"] for a in ALERT_LEVELS}


def _alert_badge(level_key: str):
    info = next((a for a in ALERT_LEVELS if a["key"] == level_key), None)
    if not info:
        return
    bg = info["color"]
    tc = "#000" if level_key in ("NO_WARNING", "ADVISORY") else "#FFF"
    st.markdown(
        f'<span style="background:{bg};color:{tc};padding:4px 14px;'
        f'border-radius:4px;font-weight:bold;font-size:13px;">'
        f'{info["label"]}</span>',
        unsafe_allow_html=True,
    )


def _collect_event_data(event_idx: int) -> dict:
    """Collect data for a single geological event."""
    prefix = f"gst_ev{event_idx}"
    all_regions = get_region_names()

    st.markdown(f"#### Event {event_idx + 1}")

    # Type + Alert Level
    hcol1, hcol2, hcol3 = st.columns([2, 2, 1])
    with hcol1:
        htype_idx = st.selectbox(
            "Hazard Type", range(len(GST_HAZARD_TYPES)),
            format_func=lambda i: GST_HAZARD_TYPES[i]["label"],
            key=f"{prefix}_type",
        )
        htype = GST_HAZARD_TYPES[htype_idx]["key"]
    with hcol2:
        levels = ALERT_LEVELS[1:]
        alert_idx = st.selectbox(
            "Alert Level", range(len(levels)),
            format_func=lambda i: levels[i]["label"],
            key=f"{prefix}_alert",
        )
        alert = levels[alert_idx]["key"]
    with hcol3:
        st.markdown("&nbsp;")
        _alert_badge(alert)

    # Earthquake-specific fields
    if htype == "EARTHQUAKE":
        eq_cols = st.columns(3)
        with eq_cols[0]:
            magnitude = st.number_input(
                "Magnitude", min_value=0.0, max_value=10.0,
                value=4.0, step=0.1, key=f"{prefix}_magnitude",
            )
        with eq_cols[1]:
            depth = st.number_input(
                "Depth (km)", min_value=0.0, max_value=700.0,
                value=10.0, step=1.0, key=f"{prefix}_depth",
            )
        with eq_cols[2]:
            severity_idx = st.selectbox(
                "Severity", range(len(GST_SEVERITY_LEVELS)),
                format_func=lambda i: GST_SEVERITY_LEVELS[i]["label"],
                index=2, key=f"{prefix}_severity",
            )
    elif htype == "VOLCANO":
        vol_cols = st.columns(2)
        with vol_cols[0]:
            vhi = st.selectbox(
                "Volcanic Hazard Index",
                ["Low", "Moderate", "High", "Very High"],
                index=1, key=f"{prefix}_vhi",
            )
        with vol_cols[1]:
            activity = st.selectbox(
                "Activity Type",
                ["Seismic Activity", "Gas Emission", "Ash Eruption",
                 "Lava Flow", "Lahar", "Full Eruption"],
                key=f"{prefix}_activity",
            )

    # Region/District selection
    alert_color = ALERT_COLOR_MAP.get(alert, "#FFFF00")
    regions_key = f"{prefix}_regions"

    selection = render_map_selector(
        key_prefix=prefix,
        sel_key=regions_key,
        color=alert_color,
        all_regions=all_regions,
        allow_districts=True,
    )

    # Description
    default_desc = DEFAULT_IMPACTS_NEW.get(htype, {}).get("en", "")
    desc = st.text_area(
        "Description", key=f"{prefix}_desc", height=80,
        placeholder=default_desc,
    )

    # Likelihood & Impact
    lcol1, lcol2 = st.columns(2)
    with lcol1:
        lik = st.selectbox("Likelihood", LIKELIHOOD_LEVELS, index=1,
                           key=f"{prefix}_lik")
    with lcol2:
        imp = st.selectbox("Impact", IMPACT_LEVELS, index=1,
                           key=f"{prefix}_imp")

    # Impacts expected
    impacts_exp = st.text_area(
        "Impacts Expected", key=f"{prefix}_impacts", height=68,
        placeholder=default_desc,
    )

    event = {
        "type": htype,
        "alert_level": alert,
        "regions": selection["regions"],
        "districts": selection["districts"],
        "description": desc,
        "likelihood": lik,
        "impact": imp,
        "impacts_expected": impacts_exp,
    }
    if htype == "EARTHQUAKE":
        event["magnitude"] = magnitude
        event["depth_km"] = depth
        event["severity"] = GST_SEVERITY_LEVELS[severity_idx]["key"]
    elif htype == "VOLCANO":
        event["volcanic_hazard_index"] = vhi
        event["activity_type"] = activity

    return event


def render_gst_page():
    """Render the GST monitoring page."""
    username = st.session_state.get("current_username", "unknown")
    offer_restore(username, "gst", "gst")
    render_template_controls("gst", "gst")

    # Issue info
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            issue_date = st.date_input("Issue Date", value=date.today(),
                                       key="gst_issue_date")
        with col2:
            issue_time = st.time_input("Issue Time", value=time(8, 0),
                                       key="gst_issue_time")

    # Alert legend
    with st.container(border=True):
        st.markdown("**Alert Level Legend:**")
        lcols = st.columns(4)
        for i, level in enumerate(ALERT_LEVELS):
            with lcols[i]:
                bg = level["color"]
                tc = "#000" if level["key"] in ("NO_WARNING", "ADVISORY") else "#FFF"
                st.markdown(
                    f'<div style="background:{bg};color:{tc};padding:8px;'
                    f'border-radius:6px;text-align:center;font-weight:bold;">'
                    f'{level["label"]}</div>',
                    unsafe_allow_html=True,
                )

    # Events
    event_count_key = "gst_event_count"
    if event_count_key not in st.session_state:
        st.session_state[event_count_key] = 1

    events = []
    for i in range(st.session_state[event_count_key]):
        with st.container(border=True):
            events.append(_collect_event_data(i))

    # Add/remove events
    acol1, acol2 = st.columns(2)
    with acol1:
        if st.button("+ Add Event", key="gst_add_ev",
                     use_container_width=True, type="primary"):
            st.session_state[event_count_key] += 1
            st.rerun()
    with acol2:
        if st.session_state[event_count_key] > 1:
            if st.button("- Remove Event", key="gst_rem_ev",
                         use_container_width=True):
                st.session_state[event_count_key] -= 1
                st.rerun()

    st.markdown("---")

    # Submit — save JSON to output
    if st.button("Submit GST Assessment", type="primary",
                 use_container_width=True, key="gst_submit"):
        data = {
            "agency": "GST",
            "issue_date": issue_date.strftime("%Y-%m-%d"),
            "issue_time": issue_time.strftime("%H:%M"),
            "events": events,
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = GST_OUTPUT_DIR / f"gst_assessment_{timestamp}.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        # Save to session for DMD bridge
        st.session_state["gst_latest_data"] = data

        st.success(f"GST Assessment saved: {out_path.name}")
        st.json(data)

        auto_save(username, "gst", "gst")

    # Link to DMD
    st.markdown("---")
    with st.container(border=True):
        st.caption(
            "GST data will be available for import in the PMO/DMD Multirisk page."
        )
        if st.button("Go to PMO/DMD Dashboard", use_container_width=True,
                     key="gst_goto_dmd"):
            st.session_state["view_selector"] = "PMO/DMD (Multirisk)"
            st.rerun()
