"""NEMC Dashboard — National Environment Management Council.

Monitors: Air Pollution (industrial emissions, wildfires, dust storms).
Region/district selection with map, AQI levels, and data export
to PMO/DMD via session state.
"""

import json
from datetime import date, time, datetime
from pathlib import Path

import streamlit as st

from .config import (
    NEMC_OUTPUT_DIR, OUTPUT_DIR,
    ALERT_LEVELS, LIKELIHOOD_LEVELS, IMPACT_LEVELS,
    NEMC_HAZARD_TYPES, DEFAULT_IMPACTS_NEW,
    get_region_names,
)
from .map_widget import render_map_selector
from .templates import render_template_controls, auto_save, offer_restore


ALERT_COLOR_MAP = {a["key"]: a["color"] for a in ALERT_LEVELS}

AQI_LEVELS = [
    {"key": "GOOD", "label": "Good (0-50)", "color": "#00E400"},
    {"key": "MODERATE", "label": "Moderate (51-100)", "color": "#FFFF00"},
    {"key": "UNHEALTHY_SG", "label": "Unhealthy for Sensitive Groups (101-150)", "color": "#FF7E00"},
    {"key": "UNHEALTHY", "label": "Unhealthy (151-200)", "color": "#FF0000"},
    {"key": "VERY_UNHEALTHY", "label": "Very Unhealthy (201-300)", "color": "#8F3F97"},
    {"key": "HAZARDOUS", "label": "Hazardous (301+)", "color": "#7E0023"},
]

POLLUTION_SOURCES = [
    "Industrial Emissions", "Vehicle Emissions", "Wildfire Smoke",
    "Dust Storm", "Agricultural Burning", "Waste Burning",
    "Volcanic Ash", "Other",
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


def _collect_pollution_data(idx: int) -> dict:
    """Collect data for an air pollution event."""
    prefix = f"nemc_ap{idx}"
    all_regions = get_region_names()

    st.markdown(f"#### Pollution Event {idx + 1}")

    # Source + Alert Level
    hcol1, hcol2, hcol3 = st.columns([2, 2, 1])
    with hcol1:
        source = st.selectbox(
            "Pollution Source", POLLUTION_SOURCES,
            key=f"{prefix}_source",
        )
        if source == "Other":
            source = st.text_input("Specify source", key=f"{prefix}_source_other")
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

    # AQI and pollutants
    aqi_cols = st.columns(3)
    with aqi_cols[0]:
        aqi_idx = st.selectbox(
            "AQI Level", range(len(AQI_LEVELS)),
            format_func=lambda i: AQI_LEVELS[i]["label"],
            index=2, key=f"{prefix}_aqi",
        )
        aqi_level = AQI_LEVELS[aqi_idx]
        st.markdown(
            f'<div style="background:{aqi_level["color"]};padding:4px 8px;'
            f'border-radius:4px;text-align:center;font-size:12px;font-weight:bold;">'
            f'{aqi_level["label"]}</div>',
            unsafe_allow_html=True,
        )
    with aqi_cols[1]:
        aqi_value = st.number_input(
            "AQI Value", min_value=0, max_value=500,
            value=120, step=10, key=f"{prefix}_aqi_val",
        )
    with aqi_cols[2]:
        pollutants = st.multiselect(
            "Key Pollutants",
            ["PM2.5", "PM10", "SO2", "NO2", "CO", "O3"],
            default=["PM2.5", "PM10"],
            key=f"{prefix}_pollutants",
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
        placeholder="Describe pollution event, source, affected population...",
    )

    # Health advisory
    advisory = st.text_area(
        "Health Advisory", key=f"{prefix}_advisory", height=68,
        placeholder="Avoid outdoor activities, use masks, close windows...",
    )

    # Likelihood & Impact
    lcol1, lcol2 = st.columns(2)
    with lcol1:
        lik = st.selectbox("Persistence Likelihood", LIKELIHOOD_LEVELS, index=1,
                           key=f"{prefix}_lik")
    with lcol2:
        imp = st.selectbox("Health Impact", IMPACT_LEVELS, index=1,
                           key=f"{prefix}_imp")

    return {
        "type": "AIR_POLLUTION",
        "source": source,
        "alert_level": alert,
        "aqi_level": aqi_level["key"],
        "aqi_value": aqi_value,
        "pollutants": pollutants,
        "regions": selection["regions"],
        "districts": selection["districts"],
        "description": desc,
        "health_advisory": advisory,
        "likelihood": lik,
        "impact": imp,
    }


def render_nemc_page():
    """Render the NEMC air pollution monitoring page."""
    username = st.session_state.get("current_username", "unknown")
    offer_restore(username, "nemc", "nemc")
    render_template_controls("nemc", "nemc")

    # Issue info
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            issue_date = st.date_input("Report Date", value=date.today(),
                                       key="nemc_issue_date")
        with col2:
            issue_time = st.time_input("Report Time", value=time(10, 0),
                                       key="nemc_issue_time")

    # AQI legend
    with st.container(border=True):
        st.markdown("**Air Quality Index (AQI) Levels:**")
        lcols = st.columns(len(AQI_LEVELS))
        for i, level in enumerate(AQI_LEVELS):
            with lcols[i]:
                st.markdown(
                    f'<div style="background:{level["color"]};padding:6px 4px;'
                    f'border-radius:4px;text-align:center;font-size:10px;'
                    f'font-weight:bold;">{level["label"].split("(")[0].strip()}</div>',
                    unsafe_allow_html=True,
                )

    # Events
    event_count_key = "nemc_event_count"
    if event_count_key not in st.session_state:
        st.session_state[event_count_key] = 1

    events = []
    for i in range(st.session_state[event_count_key]):
        with st.container(border=True):
            events.append(_collect_pollution_data(i))

    # Add/remove
    acol1, acol2 = st.columns(2)
    with acol1:
        if st.button("+ Add Event", key="nemc_add_ev",
                     use_container_width=True, type="primary"):
            st.session_state[event_count_key] += 1
            st.rerun()
    with acol2:
        if st.session_state[event_count_key] > 1:
            if st.button("- Remove Event", key="nemc_rem_ev",
                         use_container_width=True):
                st.session_state[event_count_key] -= 1
                st.rerun()

    st.markdown("---")

    # Submit
    if st.button("Submit NEMC Air Quality Report", type="primary",
                 use_container_width=True, key="nemc_submit"):
        data = {
            "agency": "NEMC",
            "report_date": issue_date.strftime("%Y-%m-%d"),
            "report_time": issue_time.strftime("%H:%M"),
            "events": events,
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = NEMC_OUTPUT_DIR / f"nemc_airquality_{timestamp}.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        st.session_state["nemc_latest_data"] = data

        st.success(f"NEMC Air Quality Report saved: {out_path.name}")
        st.json(data)

        auto_save(username, "nemc", "nemc")

    # Link to DMD
    st.markdown("---")
    with st.container(border=True):
        st.caption(
            "NEMC air quality data will be available for import in the PMO/DMD Multirisk page."
        )
        if st.button("Go to PMO/DMD Dashboard", use_container_width=True,
                     key="nemc_goto_dmd"):
            st.session_state["view_selector"] = "PMO/DMD (Multirisk)"
            st.rerun()
