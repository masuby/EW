"""MoW Dashboard — Ministry of Water Flood Risk Assessment.

Catchment/basin-based analysis with river network maps.
District selection via river basins, alert tier assignment,
and push to PMO/DMD via data bridge.
"""

import json
import io
import contextlib
from datetime import date, time, timedelta, datetime
from pathlib import Path

import streamlit as st

from .config import (
    MOW_OUTPUT_DIR, OUTPUT_DIR,
    ALERT_LEVELS, LIKELIHOOD_LEVELS, IMPACT_LEVELS,
    CATCHMENT_BASINS, get_catchment_names, get_districts_by_catchment,
    get_district_names,
)
from .common_widgets import (
    alert_level_select, likelihood_impact_row,
    district_selector_by_tier, dynamic_text_list,
)
from .templates import render_template_controls, auto_save, offer_restore
from .data_bridge import load_latest_tma


ALERT_COLOR_MAP = {a["key"]: a["color"] for a in ALERT_LEVELS}
_ALERT_RANK = {"ADVISORY": 0, "WARNING": 1, "MAJOR_WARNING": 2}


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


def _render_catchment_map(key_prefix: str, selected_basins: list[str],
                          basin_alerts: dict[str, str]):
    """Render an interactive catchment basin map with river overlay.

    Shows Tanzania districts colored by the alert level of their parent basin.
    Rivers and lakes overlaid for hydrological context.
    """
    try:
        import plotly.express as px
        import geopandas as gpd
        from .config import (
            load_districts_geodata, load_rivers_geodata,
            load_lakes_geodata, load_country_boundary,
        )
    except ImportError:
        st.warning("Plotly or geopandas not available for map rendering.")
        return

    districts_geojson = load_districts_geodata()
    by_catchment = get_districts_by_catchment()

    # Build district → (basin, alert) mapping
    district_basin = {}
    district_alert = {}
    for basin_name in selected_basins:
        alert = basin_alerts.get(basin_name, "ADVISORY")
        for dist in by_catchment.get(basin_name, []):
            # If district already assigned to a higher alert, keep the higher one
            if dist in district_alert:
                if _ALERT_RANK.get(alert, 0) > _ALERT_RANK.get(district_alert[dist], 0):
                    district_alert[dist] = alert
                    district_basin[dist] = basin_name
            else:
                district_alert[dist] = alert
                district_basin[dist] = basin_name

    # Prepare data for choropleth
    features = districts_geojson["features"]
    display_names = []
    colors = []
    hover_texts = []
    color_map = {"ADVISORY": "#FFFF00", "WARNING": "#FFA500", "MAJOR_WARNING": "#FF0000"}

    for f in features:
        name = f["properties"]["display_name"]
        display_names.append(name)
        if name in district_alert:
            alert = district_alert[name]
            colors.append(color_map.get(alert, "#E8E8E8"))
            basin = district_basin.get(name, "")
            alert_label = next(
                (a["label"] for a in ALERT_LEVELS if a["key"] == alert), alert
            )
            hover_texts.append(f"{name}<br>Basin: {basin}<br>Alert: {alert_label}")
        else:
            colors.append("#F5F5F5")
            hover_texts.append(f"{name}<br>No assessment")

    import plotly.graph_objects as go

    fig = go.Figure()

    # District choropleth
    for i, feature in enumerate(features):
        coords = feature["geometry"]["coordinates"]
        geo_type = feature["geometry"]["type"]

        def _add_polygon(coord_list, fill_color, hover, name_text):
            # Extract exterior ring
            xs = [p[0] for p in coord_list[0]]
            ys = [p[1] for p in coord_list[0]]
            fig.add_trace(go.Scattergl(
                x=xs, y=ys, fill="toself",
                fillcolor=fill_color,
                line=dict(color="#999", width=0.5),
                hovertext=hover,
                hoverinfo="text",
                name=name_text,
                showlegend=False,
                mode="lines",
            ))

        if geo_type == "Polygon":
            _add_polygon(coords, colors[i], hover_texts[i], display_names[i])
        elif geo_type == "MultiPolygon":
            for poly in coords:
                _add_polygon(poly, colors[i], hover_texts[i], display_names[i])

    # River overlay
    rivers = load_rivers_geodata()
    if rivers is not None and len(rivers) > 0:
        for _, river in rivers.iterrows():
            geom = river.geometry
            if geom is None:
                continue
            if geom.geom_type == "LineString":
                xs = [c[0] for c in geom.coords]
                ys = [c[1] for c in geom.coords]
                fig.add_trace(go.Scattergl(
                    x=xs, y=ys, mode="lines",
                    line=dict(color="#4A90D9", width=1.5),
                    hoverinfo="skip", showlegend=False,
                ))
            elif geom.geom_type == "MultiLineString":
                for line in geom.geoms:
                    xs = [c[0] for c in line.coords]
                    ys = [c[1] for c in line.coords]
                    fig.add_trace(go.Scattergl(
                        x=xs, y=ys, mode="lines",
                        line=dict(color="#4A90D9", width=1.5),
                        hoverinfo="skip", showlegend=False,
                    ))

    # Lakes overlay
    lakes = load_lakes_geodata()
    if lakes is not None and len(lakes) > 0:
        for _, lake in lakes.iterrows():
            geom = lake.geometry
            if geom is None:
                continue
            if geom.geom_type == "Polygon":
                xs = [c[0] for c in geom.exterior.coords]
                ys = [c[1] for c in geom.exterior.coords]
                fig.add_trace(go.Scattergl(
                    x=xs, y=ys, fill="toself",
                    fillcolor="rgba(176, 212, 241, 0.6)",
                    line=dict(color="#4A90D9", width=1),
                    hoverinfo="skip", showlegend=False,
                    mode="lines",
                ))
            elif geom.geom_type == "MultiPolygon":
                for poly in geom.geoms:
                    xs = [c[0] for c in poly.exterior.coords]
                    ys = [c[1] for c in poly.exterior.coords]
                    fig.add_trace(go.Scattergl(
                        x=xs, y=ys, fill="toself",
                        fillcolor="rgba(176, 212, 241, 0.6)",
                        line=dict(color="#4A90D9", width=1),
                        hoverinfo="skip", showlegend=False,
                        mode="lines",
                    ))

    fig.update_layout(
        height=500,
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False),
        plot_bgcolor="white",
        title=dict(text="Catchment Basin Assessment", font=dict(size=14)),
        dragmode="pan",
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_map",
                    config={"scrollZoom": True, "displayModeBar": False})


def _render_tma_context():
    """Show TMA weather context (read-only) for MoW reference."""
    tma_data = load_latest_tma()
    if not tma_data:
        st.info("No TMA forecast available yet. Generate TMA bulletin first.")
        return

    issue = tma_data.get("issue_date", "")
    days = tma_data.get("days", [])
    n_hazards = sum(len(d.get("hazards", [])) for d in days)

    st.markdown(
        f'<div style="padding:8px 12px;background:#e3f2fd;border-radius:6px;'
        f'border-left:4px solid #2196F3;font-size:13px;">'
        f'<b>TMA Weather Context</b> &mdash; issued {issue}, '
        f'{len(days)} days, {n_hazards} hazards</div>',
        unsafe_allow_html=True,
    )

    with st.expander("View TMA Hazards (reference)", expanded=False):
        _alert_label = {
            "ADVISORY": "Advisory", "WARNING": "Warning",
            "MAJOR_WARNING": "Major Warning",
        }
        for d_idx, day in enumerate(days[:3]):
            if d_idx >= 3:
                break
            st.markdown(f"**Day {d_idx + 1}** — {day.get('date', '')}")
            hazards = day.get("hazards", [])
            if not hazards:
                st.caption("No hazards")
                continue
            for h in hazards:
                alert = h.get("alert_level", "ADVISORY")
                htype = h.get("type", "")
                desc = h.get("description", "")
                regions = h.get("regions", [])
                al = _alert_label.get(alert, alert)
                st.markdown(
                    f"- **{htype}** ({al}): {desc} "
                    f"*[{', '.join(regions[:5])}{'...' if len(regions) > 5 else ''}]*"
                )


def _copy_day_data(source_day: int, target_day: int):
    """Copy all MoW form data from source day to target day."""
    src = f"mow_d{source_day}"
    tgt = f"mow_d{target_day}"

    # Assessment count
    src_count = st.session_state.get(f"{src}_assess_count", 1)
    st.session_state[f"{tgt}_assess_count"] = src_count

    # Each assessment's fields
    for a in range(src_count):
        for suffix in [f"_a{a}_basins", f"_a{a}_alert", f"_a{a}_desc",
                       f"_a{a}_lik", f"_a{a}_imp", f"_a{a}_districts"]:
            src_key = f"{src}{suffix}"
            tgt_key = f"{tgt}{suffix}"
            if src_key in st.session_state:
                st.session_state[tgt_key] = st.session_state[src_key]


def _collect_day_data(day_idx: int) -> dict:
    """Collect MoW assessment data for one day."""
    prefix = f"mow_d{day_idx}"
    by_catchment = get_districts_by_catchment()
    all_basins = get_catchment_names()
    all_districts = get_district_names()

    # Copy-from-day button
    if day_idx > 0:
        _, copy_col = st.columns([4, 1])
        with copy_col:
            copy_src = st.selectbox(
                "Copy from",
                [f"Day {i+1}" for i in range(day_idx)],
                key=f"{prefix}_copy_src",
            )
            if st.button("Copy", key=f"{prefix}_copy_btn", use_container_width=True):
                src_idx = int(copy_src.split()[-1]) - 1
                _copy_day_data(src_idx, day_idx)
                st.rerun()

    assessments = []
    assess_count_key = f"{prefix}_assess_count"
    if assess_count_key not in st.session_state:
        st.session_state[assess_count_key] = 1

    for a in range(st.session_state[assess_count_key]):
        st.markdown("---")
        st.markdown(f"#### Assessment {a + 1}")

        # Alert level + badge
        acol1, acol2 = st.columns([2, 1])
        with acol1:
            levels = ALERT_LEVELS[1:]  # Skip NO_WARNING
            alert_idx = st.selectbox(
                "Alert Level", range(len(levels)),
                format_func=lambda i: levels[i]["label"],
                key=f"{prefix}_a{a}_alert",
            )
            alert = levels[alert_idx]["key"]
        with acol2:
            st.markdown("&nbsp;")
            _alert_badge(alert)

        # Basin selection — quick-select buttons + multiselect
        st.markdown("**Catchment Basins**")
        basin_cols = st.columns(5)
        basins_key = f"{prefix}_a{a}_basins"
        if basins_key not in st.session_state:
            st.session_state[basins_key] = []

        for i, basin_name in enumerate(all_basins):
            label = CATCHMENT_BASINS[basin_name]["label"]
            with basin_cols[i % 5]:
                if st.button(
                    label, key=f"{prefix}_a{a}_basin_btn_{basin_name}",
                    use_container_width=True,
                ):
                    current = list(st.session_state.get(basins_key, []))
                    if basin_name not in current:
                        current.append(basin_name)
                    else:
                        current.remove(basin_name)
                    st.session_state[basins_key] = current
                    st.rerun()

        selected_basins = st.multiselect(
            "Selected Basins", all_basins,
            key=basins_key,
            format_func=lambda b: CATCHMENT_BASINS[b]["label"],
            label_visibility="collapsed",
        )

        # Auto-expand basins to districts
        auto_districts = []
        for basin in selected_basins:
            for dist in by_catchment.get(basin, []):
                if dist not in auto_districts:
                    auto_districts.append(dist)

        # District multiselect — pre-filled from basins, officer can adjust
        districts_key = f"{prefix}_a{a}_districts"
        if selected_basins and districts_key not in st.session_state:
            st.session_state[districts_key] = sorted(auto_districts)

        # Sync: when basins change, update districts
        prev_basins_key = f"{prefix}_a{a}_prev_basins"
        if st.session_state.get(prev_basins_key) != selected_basins:
            st.session_state[districts_key] = sorted(auto_districts)
            st.session_state[prev_basins_key] = list(selected_basins)

        selected_districts = st.multiselect(
            "Affected Districts (auto-filled from basins, adjust as needed)",
            all_districts,
            key=districts_key,
        )

        if selected_basins:
            st.caption(
                f"{len(selected_basins)} basin(s) → "
                f"{len(selected_districts)} district(s)"
            )

        # Description
        desc = st.text_area(
            "Description", key=f"{prefix}_a{a}_desc", height=80,
            placeholder="River levels in the Rufiji basin are rising above threshold...",
            help="Describe the flood/water risk based on your analysis.",
        )

        # Likelihood & Impact
        lcol1, lcol2 = st.columns(2)
        with lcol1:
            lik = st.selectbox("Likelihood", LIKELIHOOD_LEVELS, index=1,
                               key=f"{prefix}_a{a}_lik")
        with lcol2:
            imp = st.selectbox("Impact", IMPACT_LEVELS, index=1,
                               key=f"{prefix}_a{a}_imp")

        assessments.append({
            "basins": selected_basins,
            "alert_level": alert,
            "districts": selected_districts,
            "description": desc,
            "likelihood": lik,
            "impact": imp,
        })

    # Add/remove assessment
    acol1, acol2 = st.columns(2)
    with acol1:
        if st.button("+ Add Assessment", key=f"{prefix}_add_assess",
                     use_container_width=True, type="primary"):
            st.session_state[assess_count_key] += 1
            st.rerun()
    with acol2:
        if st.session_state[assess_count_key] > 1:
            if st.button("- Remove Assessment", key=f"{prefix}_rem_assess",
                         use_container_width=True):
                st.session_state[assess_count_key] -= 1
                st.rerun()

    return {"assessments": assessments}


def _build_json(issue_date: date, issue_time: time, day_data: list[dict]) -> dict:
    """Build MoW JSON from collected form data."""
    days = []
    for d, dd in enumerate(day_data):
        forecast_date = issue_date + timedelta(days=d)
        day_json = {
            "day_number": d + 1,
            "date": forecast_date.strftime("%Y-%m-%d"),
            "assessments": [],
        }
        for assessment in dd.get("assessments", []):
            day_json["assessments"].append({
                "basins": assessment.get("basins", []),
                "alert_level": assessment.get("alert_level", "ADVISORY"),
                "districts": assessment.get("districts", []),
                "description": assessment.get("description", ""),
                "likelihood": assessment.get("likelihood", "MEDIUM"),
                "impact": assessment.get("impact", "MEDIUM"),
            })
        days.append(day_json)

    return {
        "source": "mow",
        "issue_date": issue_date.strftime("%Y-%m-%d"),
        "issue_time": issue_time.strftime("%H:%M"),
        "days": days,
    }


def render_mow_page():
    """Render the MoW (Ministry of Water) dashboard."""
    username = st.session_state.get("current_username", "unknown")

    # Session restore
    offer_restore(username, "mow", "mow")

    # Template controls in sidebar
    render_template_controls("mow", "mow")

    st.markdown("## Ministry of Water — Flood Risk Assessment")
    st.caption("Catchment Basin Analysis — 3-Day Forecast")

    # --- TMA Context (read-only reference) ---
    with st.container(border=True):
        _render_tma_context()

    st.markdown("---")

    # --- Issue info ---
    with st.container(border=True):
        st.subheader("Assessment Details")
        col1, col2 = st.columns(2)
        with col1:
            issue_date = st.date_input("Issue Date", value=date.today(),
                                       key="mow_issue_date")
        with col2:
            issue_time = st.time_input("Issue Time", value=time(10, 0),
                                       key="mow_issue_time")

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

    # --- Day tabs ---
    day_labels = [
        f"Day {d+1} ({(issue_date + timedelta(days=d)).strftime('%a %d/%m')})"
        for d in range(3)
    ]
    tabs = st.tabs(day_labels)
    all_day_data = []

    for d, tab in enumerate(tabs):
        with tab:
            day_data = _collect_day_data(d)
            all_day_data.append(day_data)

            # Show map preview for this day's assessments
            assessments = day_data.get("assessments", [])
            if any(a.get("basins") for a in assessments):
                selected_basins = []
                basin_alerts = {}
                for a in assessments:
                    for basin in a.get("basins", []):
                        if basin not in selected_basins:
                            selected_basins.append(basin)
                        # Keep highest alert for each basin
                        existing = basin_alerts.get(basin, "ADVISORY")
                        new = a.get("alert_level", "ADVISORY")
                        if _ALERT_RANK.get(new, 0) > _ALERT_RANK.get(existing, 0):
                            basin_alerts[basin] = new

                with st.expander("Map Preview", expanded=True):
                    _render_catchment_map(
                        f"mow_d{d}_preview",
                        selected_basins,
                        basin_alerts,
                    )

                    # Summary
                    all_districts = set()
                    for a in assessments:
                        all_districts.update(a.get("districts", []))
                    st.caption(
                        f"{len(selected_basins)} basin(s), "
                        f"{len(all_districts)} district(s) affected"
                    )

    st.markdown("---")

    # --- Push to DMD ---
    if st.button("Push Assessment to PMO/DMD", type="primary",
                 use_container_width=True, key="mow_push"):
        json_data = _build_json(issue_date, issue_time, all_day_data)

        from .data_bridge import save_mow_for_dmd
        save_mow_for_dmd(json_data)

        # Save JSON to output
        MOW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = MOW_OUTPUT_DIR / f"mow_assessment_{timestamp}.json"
        output_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False))

        # Auto-save
        auto_save(username, "mow", "mow")

        # Audit log
        from .audit import log_generation
        log_generation(
            username, st.session_state.get("current_role", "unknown"),
            "mow", json_data, {"result": {"json": str(output_path)},
                               "error": None, "duration": 0},
            0,
        )

        st.success(
            "Assessment pushed to PMO/DMD! The DMD officer will see your "
            "flood risk data as an input layer."
        )
        st.balloons()

        # Show summary
        with st.container(border=True):
            st.markdown("**Pushed Assessment Summary:**")
            for d_idx, dd in enumerate(all_day_data):
                assessments = dd.get("assessments", [])
                districts = set()
                for a in assessments:
                    districts.update(a.get("districts", []))
                st.markdown(
                    f"- **Day {d_idx+1}**: {len(assessments)} assessment(s), "
                    f"{len(districts)} district(s)"
                )

    # --- Link to PMO/DMD ---
    st.markdown("---")
    with st.container(border=True):
        st.markdown(
            '<div style="display:flex;align-items:center;gap:0.5rem;">'
            '<span style="font-size:1.3rem;">&#10145;</span>'
            '<span style="font-size:1rem;font-weight:600;">'
            "Proceed to PMO/DMD Dashboard</span></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "MoW flood risk data will be available as an input layer "
            "in the DMD analysis view."
        )
        if st.button(
            "Go to PMO/DMD Dashboard",
            type="primary",
            use_container_width=True,
            key="mow_goto_dmd",
        ):
            st.session_state["view_selector"] = "PMO/DMD (Multirisk)"
            st.rerun()
