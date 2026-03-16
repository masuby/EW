"""MoH Dashboard — Ministry of Health Disease Outbreak Monitoring.

Monitors: Disease Outbreaks (Cholera, Dengue, Malaria surges, etc.)
Region/district selection with map, outbreak details, and data export
to PMO/DMD via session state.
"""

import json
from datetime import date, time, datetime
from pathlib import Path

import streamlit as st

from .config import (
    MOH_OUTPUT_DIR, OUTPUT_DIR,
    ALERT_LEVELS, LIKELIHOOD_LEVELS, IMPACT_LEVELS,
    MOH_HAZARD_TYPES, DEFAULT_IMPACTS_NEW,
    get_region_names,
)
from .map_widget import render_map_selector
from .templates import render_template_controls, auto_save, offer_restore


ALERT_COLOR_MAP = {a["key"]: a["color"] for a in ALERT_LEVELS}

DISEASE_TYPES = [
    "Cholera", "Dengue Fever", "Malaria Surge", "Rift Valley Fever",
    "Plague", "Ebola", "Measles", "COVID-19", "Typhoid",
    "Anthrax", "Rabies", "Yellow Fever", "Other",
]


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


def _collect_outbreak_data(idx: int) -> dict:
    """Collect data for a single disease outbreak event."""
    prefix = f"moh_ob{idx}"
    all_regions = get_region_names()

    st.markdown(f"#### Outbreak {idx + 1}")

    # Disease type + Alert Level
    hcol1, hcol2, hcol3 = st.columns([2, 2, 1])
    with hcol1:
        disease = st.selectbox(
            "Disease", DISEASE_TYPES,
            key=f"{prefix}_disease",
        )
        if disease == "Other":
            disease = st.text_input("Specify disease", key=f"{prefix}_disease_other")
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

    # Outbreak-specific fields
    ob_cols = st.columns(3)
    with ob_cols[0]:
        cases = st.number_input(
            "Confirmed Cases", min_value=0,
            value=0, step=1, key=f"{prefix}_cases",
        )
    with ob_cols[1]:
        deaths = st.number_input(
            "Deaths", min_value=0,
            value=0, step=1, key=f"{prefix}_deaths",
        )
    with ob_cols[2]:
        trend = st.selectbox(
            "Trend", ["Increasing", "Stable", "Decreasing"],
            key=f"{prefix}_trend",
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
    desc = st.text_area(
        "Situation Summary", key=f"{prefix}_desc", height=80,
        placeholder="Describe the outbreak situation, transmission pattern, and response status...",
    )

    # Response actions
    response = st.text_area(
        "Response Actions", key=f"{prefix}_response", height=68,
        placeholder="Describe ongoing response actions (vaccination, isolation, water treatment, etc.)...",
    )

    # Likelihood & Impact
    lcol1, lcol2 = st.columns(2)
    with lcol1:
        lik = st.selectbox("Spread Likelihood", LIKELIHOOD_LEVELS, index=1,
                           key=f"{prefix}_lik")
    with lcol2:
        imp = st.selectbox("Health Impact", IMPACT_LEVELS, index=1,
                           key=f"{prefix}_imp")

    return {
        "type": "DISEASE_OUTBREAK",
        "disease": disease,
        "alert_level": alert,
        "confirmed_cases": cases,
        "deaths": deaths,
        "trend": trend,
        "regions": selection["regions"],
        "districts": selection["districts"],
        "description": desc,
        "response_actions": response,
        "likelihood": lik,
        "impact": imp,
    }


def render_moh_page():
    """Render the MoH disease outbreak monitoring page."""
    username = st.session_state.get("current_username", "unknown")
    offer_restore(username, "moh", "moh")
    render_template_controls("moh", "moh")

    # Issue info
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            issue_date = st.date_input("Report Date", value=date.today(),
                                       key="moh_issue_date")
        with col2:
            issue_time = st.time_input("Report Time", value=time(9, 0),
                                       key="moh_issue_time")

    # Alert legend
    with st.container(border=True):
        st.markdown("**Outbreak Alert Levels:**")
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

    # Outbreaks
    ob_count_key = "moh_outbreak_count"
    if ob_count_key not in st.session_state:
        st.session_state[ob_count_key] = 1

    outbreaks = []
    for i in range(st.session_state[ob_count_key]):
        with st.container(border=True):
            outbreaks.append(_collect_outbreak_data(i))

    # Add/remove
    acol1, acol2 = st.columns(2)
    with acol1:
        if st.button("+ Add Outbreak", key="moh_add_ob",
                     use_container_width=True, type="primary"):
            st.session_state[ob_count_key] += 1
            st.rerun()
    with acol2:
        if st.session_state[ob_count_key] > 1:
            if st.button("- Remove Outbreak", key="moh_rem_ob",
                         use_container_width=True):
                st.session_state[ob_count_key] -= 1
                st.rerun()

    st.markdown("---")

    # Submit
    if st.button("Submit MoH Outbreak Report", type="primary",
                 use_container_width=True, key="moh_submit"):
        data = {
            "agency": "MoH",
            "report_date": issue_date.strftime("%Y-%m-%d"),
            "report_time": issue_time.strftime("%H:%M"),
            "outbreaks": outbreaks,
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = MOH_OUTPUT_DIR / f"moh_outbreak_{timestamp}.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        st.session_state["moh_latest_data"] = data

        st.success(f"MoH Outbreak Report saved: {out_path.name}")
        st.json(data)

        auto_save(username, "moh", "moh")

    # Link to DMD
    st.markdown("---")
    with st.container(border=True):
        st.caption(
            "MoH outbreak data will be available for import in the PMO/DMD Multirisk page."
        )
        if st.button("Go to PMO/DMD Dashboard", use_container_width=True,
                     key="moh_goto_dmd"):
            st.session_state["view_selector"] = "PMO/DMD (Multirisk)"
            st.rerun()
