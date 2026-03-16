"""MoA Dashboard — Ministry of Agriculture Drought Monitoring.

Monitors: Drought conditions, crop impacts, food security.
Region/district selection with map, drought indicators, and data export
to PMO/DMD via session state.
"""

import json
from datetime import date, time, datetime
from pathlib import Path

import streamlit as st

from .config import (
    MOA_OUTPUT_DIR, OUTPUT_DIR,
    ALERT_LEVELS, LIKELIHOOD_LEVELS, IMPACT_LEVELS,
    MOA_HAZARD_TYPES, DEFAULT_IMPACTS_NEW,
    get_region_names,
)
from .map_widget import render_map_selector
from .templates import render_template_controls, auto_save, offer_restore


ALERT_COLOR_MAP = {a["key"]: a["color"] for a in ALERT_LEVELS}

DROUGHT_SEVERITY = [
    "D0 — Abnormally Dry",
    "D1 — Moderate Drought",
    "D2 — Severe Drought",
    "D3 — Extreme Drought",
    "D4 — Exceptional Drought",
]

AFFECTED_SECTORS = [
    "Crops", "Livestock", "Water Supply", "Pasture",
    "Food Security", "Fisheries",
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


def _collect_drought_data(idx: int) -> dict:
    """Collect data for a drought assessment area."""
    prefix = f"moa_dr{idx}"
    all_regions = get_region_names()

    st.markdown(f"#### Assessment Area {idx + 1}")

    # Severity + Alert Level
    hcol1, hcol2, hcol3 = st.columns([2, 2, 1])
    with hcol1:
        severity = st.selectbox(
            "Drought Severity", DROUGHT_SEVERITY,
            index=1, key=f"{prefix}_severity",
        )
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

    # Drought indicators
    ind_cols = st.columns(3)
    with ind_cols[0]:
        rainfall_pct = st.number_input(
            "Rainfall (% of normal)", min_value=0, max_value=200,
            value=60, step=5, key=f"{prefix}_rainfall",
        )
    with ind_cols[1]:
        ndvi = st.selectbox(
            "Vegetation (NDVI)",
            ["Normal", "Below Normal", "Poor", "Very Poor"],
            index=1, key=f"{prefix}_ndvi",
        )
    with ind_cols[2]:
        affected_sectors = st.multiselect(
            "Affected Sectors", AFFECTED_SECTORS,
            default=["Crops", "Livestock"],
            key=f"{prefix}_sectors",
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
        placeholder="Describe drought conditions, crop status, water availability...",
    )

    # Recommended actions
    actions = st.text_area(
        "Recommended Actions", key=f"{prefix}_actions", height=68,
        placeholder="Food distribution, water trucking, livestock destocking...",
    )

    # Likelihood & Impact
    lcol1, lcol2 = st.columns(2)
    with lcol1:
        lik = st.selectbox("Worsening Likelihood", LIKELIHOOD_LEVELS, index=1,
                           key=f"{prefix}_lik")
    with lcol2:
        imp = st.selectbox("Food Security Impact", IMPACT_LEVELS, index=1,
                           key=f"{prefix}_imp")

    return {
        "type": "DROUGHT",
        "severity": severity,
        "alert_level": alert,
        "rainfall_pct_normal": rainfall_pct,
        "vegetation_ndvi": ndvi,
        "affected_sectors": affected_sectors,
        "regions": selection["regions"],
        "districts": selection["districts"],
        "description": desc,
        "recommended_actions": actions,
        "likelihood": lik,
        "impact": imp,
    }


def render_moa_page():
    """Render the MoA drought monitoring page."""
    username = st.session_state.get("current_username", "unknown")
    offer_restore(username, "moa", "moa")
    render_template_controls("moa", "moa")

    # Issue info
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            issue_date = st.date_input("Report Date", value=date.today(),
                                       key="moa_issue_date")
        with col2:
            report_period = st.selectbox(
                "Report Period",
                ["Weekly", "Bi-weekly", "Monthly", "Seasonal"],
                key="moa_period",
            )

    # Alert legend
    with st.container(border=True):
        st.markdown("**Drought Alert Levels:**")
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

    # Assessment areas
    area_count_key = "moa_area_count"
    if area_count_key not in st.session_state:
        st.session_state[area_count_key] = 1

    areas = []
    for i in range(st.session_state[area_count_key]):
        with st.container(border=True):
            areas.append(_collect_drought_data(i))

    # Add/remove
    acol1, acol2 = st.columns(2)
    with acol1:
        if st.button("+ Add Area", key="moa_add_area",
                     use_container_width=True, type="primary"):
            st.session_state[area_count_key] += 1
            st.rerun()
    with acol2:
        if st.session_state[area_count_key] > 1:
            if st.button("- Remove Area", key="moa_rem_area",
                         use_container_width=True):
                st.session_state[area_count_key] -= 1
                st.rerun()

    st.markdown("---")

    # Submit
    if st.button("Submit MoA Drought Assessment", type="primary",
                 use_container_width=True, key="moa_submit"):
        data = {
            "agency": "MoA",
            "report_date": issue_date.strftime("%Y-%m-%d"),
            "report_period": report_period,
            "assessments": areas,
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = MOA_OUTPUT_DIR / f"moa_drought_{timestamp}.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        st.session_state["moa_latest_data"] = data

        st.success(f"MoA Drought Assessment saved: {out_path.name}")
        st.json(data)

        auto_save(username, "moa", "moa")

    # Link to DMD
    st.markdown("---")
    with st.container(border=True):
        st.caption(
            "MoA drought data will be available for import in the PMO/DMD Multirisk page."
        )
        if st.button("Go to PMO/DMD Dashboard", use_container_width=True,
                     key="moa_goto_dmd"):
            st.session_state["view_selector"] = "PMO/DMD (Multirisk)"
            st.rerun()
