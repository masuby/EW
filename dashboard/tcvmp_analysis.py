"""TCVMP Analysis Page — Full TCVMP functionality with agency hazard layers.

Replicates the TCVMP (Tanzania Climate Vulnerability Maps) interface inside
the EW dashboard.  Instead of climate scenario rasters, the hazard layers are
real-time alerts pushed by TMA, MoW, and other agencies.

Enhanced layout:
  KPI row       : population at risk, facilities, EAD, districts flagged
  3-column      : layer controls | interactive map | quick analysis
  Full-width    : detailed analysis tabs (Infrastructure, Flood Risk,
                  Climate, Transport)
"""

import json
import math
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as st_html
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium
import pydeck as pdk

from .tcvmp_bridge import (
    is_tcvmp_available, get_district_facility_counts,
    get_facility_points, get_flood_risk_by_district,
    get_flood_risk_totals, get_spatial_exposure_summary,
    get_exposure_summary, FACILITY_LAYERS, DEFAULT_ANALYSIS_LAYERS,
    get_population_at_risk, get_education_type_breakdown,
    get_water_type_breakdown, get_flood_depth_distribution,
    get_flood_ead_by_district, get_climate_indicators_for_districts,
    get_road_km_summary, get_railway_summary,
    get_flood_risk_hotspots, get_flood_risk_facilities,
    _run_sql,
)
from .data_bridge import load_latest_tma, load_latest_mow
from .config import (
    get_districts_by_region, _clean_region_name,
    load_districts_geodata, CATCHMENT_BASINS,
)


# ── Alert styling ──────────────────────────────────────────────────
_ALERT_COLORS = {
    "ADVISORY": "#FFFF00",
    "WARNING": "#FFA500",
    "MAJOR_WARNING": "#FF0000",
}
_ALERT_LABEL = {
    "ADVISORY": "Advisory",
    "WARNING": "Warning",
    "MAJOR_WARNING": "Major Warning",
}
_ALERT_RANK = {"ADVISORY": 0, "WARNING": 1, "MAJOR_WARNING": 2}

# ── Hazard icon mapping ──────────────────────────────────────────
_ICONS_DIR = Path(__file__).parent.parent / "assets" / "icons"

_HAZARD_ICON_FILES = {
    "HEAVY_RAIN": "heavy_rain",
    "LARGE_WAVES": "large_waves",
    "STRONG_WIND": "strong_wind",
    "FLOODS": "floods",
    "LANDSLIDES": "landslides",
    "EXTREME_TEMPERATURE": "extreme_temperature",
}

_HAZARD_LABELS = {
    "HEAVY_RAIN": "Heavy Rain",
    "LARGE_WAVES": "Large Waves",
    "STRONG_WIND": "Strong Wind",
    "FLOODS": "Floods",
    "LANDSLIDES": "Landslides",
    "EXTREME_TEMPERATURE": "Extreme Temp.",
}


def _hazard_icon_b64(hazard_type: str, size: int = 64) -> str:
    """Return base64-encoded PNG data URI for a hazard icon."""
    import base64
    stem = _HAZARD_ICON_FILES.get(hazard_type)
    if not stem:
        return ""
    suffix = f"_{size}" if size != 256 else ""
    path = _ICONS_DIR / f"{stem}{suffix}.png"
    if not path.exists():
        path = _ICONS_DIR / f"{stem}.png"
    if not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{b64}"


# ── Facility markers config ───────────────────────────────────────
_FAC_ICONS = {
    "phc_health_facilities": ("plus", "red", "Health"),
    "phc_education_facilities": ("graduation-cap", "blue", "Education"),
    "phc_water_facilities": ("tint", "cadetblue", "Water"),
    "phc_markets": ("shopping-cart", "orange", "Markets"),
    "phc_government_offices": ("building", "purple", "Gov Offices"),
    "airports": ("plane", "darkred", "Airports"),
    "sea_ports": ("ship", "darkblue", "Sea Ports"),
}


def _build_agency_alerts(issue_date: date) -> dict:
    """Build district->alert mapping from all agency data.

    Returns: {day_idx: {district_name: {"agency", "alert_level", "detail"}}}
    """
    tma_data = load_latest_tma()
    mow_data = load_latest_mow()
    by_region = get_districts_by_region()

    days = {}
    for d in range(3):
        alerts = {}

        # TMA hazards -> districts
        if tma_data and tma_data.get("days"):
            tma_days = tma_data["days"]
            if d < len(tma_days):
                for hazard in tma_days[d].get("hazards", []):
                    level = hazard.get("alert_level", "ADVISORY")
                    htype = hazard.get("type", "")
                    desc = hazard.get("description", "")
                    for r in hazard.get("regions", []):
                        display = _clean_region_name(r)
                        for dist in by_region.get(display, []):
                            existing = alerts.get(dist)
                            if not existing or _ALERT_RANK.get(level, 0) > _ALERT_RANK.get(
                                existing["alert_level"], 0
                            ):
                                alerts[dist] = {
                                    "agency": "TMA",
                                    "alert_level": level,
                                    "hazard_type": htype,
                                    "detail": f"{htype}: {desc}" if desc else htype,
                                }

        # MoW assessments -> districts
        if mow_data and mow_data.get("days"):
            mow_days = mow_data["days"]
            if d < len(mow_days):
                for assessment in mow_days[d].get("assessments", []):
                    level = assessment.get("alert_level", "ADVISORY")
                    desc = assessment.get("description", "")
                    for dist in assessment.get("districts", []):
                        existing = alerts.get(dist)
                        if not existing or _ALERT_RANK.get(level, 0) > _ALERT_RANK.get(
                            existing["alert_level"], 0
                        ):
                            alerts[dist] = {
                                "agency": "MoW",
                                "alert_level": level,
                                "hazard_type": "FLOODS",
                                "detail": desc,
                            }

        days[d] = alerts
    return days


# ═══════════════════════════════════════════════════════════════════
# MAP BUILDER
# ═══════════════════════════════════════════════════════════════════

def _build_map(district_alerts: dict, active_layers: list,
               all_districts: list, show_hotspots: bool = False,
               show_roads: bool = False) -> folium.Map:
    """Build folium map with agency hazard overlay + infrastructure layers."""
    m = folium.Map(
        location=[-6.5, 35.0],
        zoom_start=6,
        tiles=None,
        control_scale=True,
    )

    # Base maps
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="ESRI", name="Satellite",
    ).add_to(m)
    folium.TileLayer("cartodbpositron", name="Light").add_to(m)
    folium.TileLayer("cartodbdark_matter", name="Dark").add_to(m)

    # -- District boundaries with hazard colouring --
    geojson_data = load_districts_geodata()
    if geojson_data:
        hazard_group = folium.FeatureGroup(name="Agency Hazard Alerts", show=True)

        for feature in geojson_data["features"]:
            name = feature["properties"]["display_name"]
            info = district_alerts.get(name)

            if info:
                level = info["alert_level"]
                color = _ALERT_COLORS.get(level, "#CCC")
                fill_opacity = (0.5 if level == "MAJOR_WARNING"
                                else 0.35 if level == "WARNING" else 0.25)
                ht = info.get("hazard_type", "")
                h_icon_uri = _hazard_icon_b64(ht, size=64)
                h_label = _HAZARD_LABELS.get(ht, "")
                icon_img = (
                    f'<img src="{h_icon_uri}" '
                    f'style="width:28px;height:28px;vertical-align:middle;'
                    f'margin-right:6px;"/>'
                    if h_icon_uri else ""
                )
                popup_html = (
                    f'{icon_img}<b>{name}</b><br>'
                    f'Agency: {info["agency"]}<br>'
                    f'Level: {_ALERT_LABEL.get(level, level)}<br>'
                    f'Hazard: {h_label}<br>'
                    f'{info.get("detail", "")}'
                )
            else:
                color = "#999"
                fill_opacity = 0.05
                popup_html = f"<b>{name}</b><br>No alert"

            folium.GeoJson(
                feature,
                style_function=lambda x, c=color, fo=fill_opacity: {
                    "fillColor": c,
                    "color": "#666",
                    "weight": 0.8,
                    "fillOpacity": fo,
                },
                tooltip=name,
                popup=folium.Popup(popup_html, max_width=300),
            ).add_to(hazard_group)

        hazard_group.add_to(m)

    # -- Infrastructure layers from TCVMP --
    affected = list(district_alerts.keys()) if district_alerts else []
    if not affected:
        affected = all_districts[:20] if all_districts else []

    for table_name in active_layers:
        fac_config = _FAC_ICONS.get(table_name)
        if not fac_config or not affected:
            continue

        icon_name, color, label = fac_config
        points = get_facility_points(tuple(sorted(affected)), table_name, limit=400)
        if not points:
            continue

        cluster = MarkerCluster(name=f"{label} ({len(points)})", show=True)
        for pt in points:
            folium.Marker(
                location=[pt["lat"], pt["lon"]],
                popup=f"<b>{pt['name']}</b><br>{label}<br>{pt['district']}",
                tooltip=pt["name"],
                icon=folium.Icon(icon=icon_name, prefix="fa", color=color,
                                 icon_color="white"),
            ).add_to(cluster)
        cluster.add_to(m)

    # -- Flood risk hotspots --
    if show_hotspots and affected:
        hotspots = get_flood_risk_hotspots(tuple(sorted(affected)), limit=25)
        if hotspots:
            hotspot_group = folium.FeatureGroup(
                name=f"Flood Risk Hotspots ({len(hotspots)})", show=True
            )
            # Heatmap layer
            heat_data = [[h["lat"], h["lon"], h["ead"]] for h in hotspots]
            HeatMap(
                heat_data,
                name="Risk Heatmap",
                radius=20,
                blur=15,
                gradient={0.2: 'yellow', 0.5: 'orange', 0.8: 'red', 1.0: 'darkred'},
            ).add_to(m)
            # Individual markers
            for h in hotspots:
                ead_text = (f"TZS {h['ead']/1e6:.2f}M" if h["ead"] >= 1e6
                            else f"TZS {h['ead']:,.0f}")
                folium.CircleMarker(
                    location=[h["lat"], h["lon"]],
                    radius=max(4, min(15, h["depth"] * 2.5)),
                    color="#B71C1C",
                    fill=True,
                    fill_color="#FF5252",
                    fill_opacity=0.7,
                    popup=(
                        f"<b>{h['name']}</b><br>"
                        f"District: {h['district']}<br>"
                        f"EAD: {ead_text}<br>"
                        f"Depth RP100: {h['depth']:.2f}m<br>"
                        f"Damage: TZS {h['damage']:,.0f}"
                    ),
                    tooltip=f"{h['name']} (EAD: {ead_text})",
                ).add_to(hotspot_group)
            hotspot_group.add_to(m)

    # -- Road network overlay --
    if show_roads and affected:
        from .tcvmp_bridge import get_roads_in_districts
        roads = get_roads_in_districts(tuple(sorted(affected)))
        if roads:
            road_group = folium.FeatureGroup(
                name=f"Primary Roads ({len(roads)})", show=True
            )
            road_colors = {
                "trunk": "#E65100",
                "primary": "#F57C00",
                "trunk_link": "#FFB74D",
                "primary_link": "#FFE0B2",
            }
            for road in roads:
                try:
                    geojson = json.loads(road["geojson"])
                    folium.GeoJson(
                        geojson,
                        style_function=lambda x, rt=road["type"]: {
                            "color": road_colors.get(rt, "#999"),
                            "weight": 3 if rt == "trunk" else 2,
                            "opacity": 0.8,
                        },
                        tooltip=f"{road['name']} ({road['type']}) — {road['km']:.1f} km",
                    ).add_to(road_group)
                except (json.JSONDecodeError, KeyError):
                    continue
            road_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


# ═══════════════════════════════════════════════════════════════════
# LIGHTWEIGHT COMPARISON MAP (no st_folium overhead)
# ═══════════════════════════════════════════════════════════════════

_BASE_TILES = {
    "OpenStreetMap": ("OpenStreetMap", None, None),
    "Satellite": (
        None,
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "ESRI",
    ),
    "Light": ("cartodbpositron", None, None),
    "Dark": ("cartodbdark_matter", None, None),
}


def _build_compare_map(
    district_alerts: dict,
    base_map: str = "Satellite",
    show_hotspots: bool = False,
) -> str:
    """Build a lightweight folium map and return raw HTML string.

    Skips MarkerCluster / facility points / roads to keep rendering fast.
    Only draws district polygons with alert colours + optional hotspot dots.
    """
    builtin, url, attr = _BASE_TILES.get(base_map, _BASE_TILES["Satellite"])
    if builtin:
        m = folium.Map(location=[-6.5, 35.0], zoom_start=6, tiles=builtin)
    else:
        m = folium.Map(location=[-6.5, 35.0], zoom_start=6, tiles=url, attr=attr)

    geojson_data = load_districts_geodata()
    if geojson_data:
        for feature in geojson_data["features"]:
            name = feature["properties"]["display_name"]
            info = district_alerts.get(name)
            if info:
                level = info["alert_level"]
                color = _ALERT_COLORS.get(level, "#CCC")
                fill_opacity = (
                    0.5 if level == "MAJOR_WARNING"
                    else 0.35 if level == "WARNING" else 0.25
                )
            else:
                color = "#999"
                fill_opacity = 0.03
            folium.GeoJson(
                feature,
                style_function=lambda x, c=color, fo=fill_opacity: {
                    "fillColor": c, "color": "#666",
                    "weight": 0.6, "fillOpacity": fo,
                },
                tooltip=name,
            ).add_to(m)

    if show_hotspots and district_alerts:
        affected = list(district_alerts.keys())
        hotspots = get_flood_risk_hotspots(tuple(sorted(affected)), limit=15)
        if hotspots:
            for h in hotspots:
                folium.CircleMarker(
                    location=[h["lat"], h["lon"]],
                    radius=max(3, min(10, h["depth"] * 2)),
                    color="#B71C1C", fill=True,
                    fill_color="#FF5252", fill_opacity=0.6,
                    tooltip=h["name"],
                ).add_to(m)

    return m._repr_html_()


# ═══════════════════════════════════════════════════════════════════
# 3D SATELLITE MAP (pydeck)
# ═══════════════════════════════════════════════════════════════════

_ALERT_HEIGHT = {"MAJOR_WARNING": 8000, "WARNING": 5000, "ADVISORY": 3000}
_ALERT_RGB = {
    "MAJOR_WARNING": [255, 0, 0, 140],
    "WARNING": [255, 165, 0, 120],
    "ADVISORY": [255, 255, 0, 100],
}
_ALERT_RGB_LINE = {
    "MAJOR_WARNING": [200, 0, 0, 220],
    "WARNING": [200, 130, 0, 200],
    "ADVISORY": [200, 200, 0, 180],
}


def _polygon_coords(geometry: dict) -> list:
    """Extract polygon coordinates from GeoJSON geometry."""
    gtype = geometry.get("type", "")
    coords = geometry.get("coordinates", [])
    if gtype == "Polygon":
        return [coords[0]]  # outer ring
    elif gtype == "MultiPolygon":
        return [poly[0] for poly in coords]  # outer ring of each part
    return []


def _build_3d_map(district_alerts: dict, active_layers: list,
                  all_districts: list, show_hotspots: bool = False,
                  show_roads: bool = False,
                  base_map: str = "Satellite") -> pdk.Deck:
    """Build 3D satellite map using pydeck.

    Features:
      - ESRI satellite imagery base
      - Extruded district polygons (height = alert severity)
      - 3D facility columns (height = count)
      - Flood risk hotspot pillars
      - Road network paths
      - Interactive pitch/bearing rotation
    """
    layers = []

    # -- District boundaries: extruded by alert level --
    geojson_data = load_districts_geodata()
    if geojson_data:
        district_features = []
        for feature in geojson_data["features"]:
            name = feature["properties"]["display_name"]
            info = district_alerts.get(name)
            polys = _polygon_coords(feature["geometry"])

            for poly_ring in polys:
                if info:
                    level = info["alert_level"]
                    fill = _ALERT_RGB.get(level, [150, 150, 150, 40])
                    line = _ALERT_RGB_LINE.get(level, [100, 100, 100, 100])
                    height = _ALERT_HEIGHT.get(level, 1000)
                else:
                    fill = [180, 180, 180, 25]
                    line = [120, 120, 120, 60]
                    height = 200

                district_features.append({
                    "polygon": poly_ring,
                    "name": name,
                    "fill": fill,
                    "line": line,
                    "height": height,
                    "level": info["alert_level"] if info else "none",
                    "agency": info["agency"] if info else "",
                    "detail": info.get("detail", "") if info else "",
                })

        if district_features:
            layers.append(pdk.Layer(
                "PolygonLayer",
                data=district_features,
                get_polygon="polygon",
                get_fill_color="fill",
                get_line_color="line",
                get_elevation="height",
                elevation_scale=1,
                extruded=True,
                wireframe=True,
                line_width_min_pixels=1,
                pickable=True,
                auto_highlight=True,
                highlight_color=[255, 255, 255, 80],
            ))

    # -- Facility points as 3D columns --
    affected = list(district_alerts.keys()) if district_alerts else []
    if not affected:
        affected = all_districts[:20] if all_districts else []

    _fac_rgb = {
        "phc_health_facilities": [229, 57, 53],
        "phc_education_facilities": [30, 136, 229],
        "phc_water_facilities": [0, 172, 193],
        "phc_markets": [245, 124, 0],
        "phc_government_offices": [94, 53, 177],
        "airports": [109, 76, 65],
        "sea_ports": [2, 119, 189],
    }
    _fac_label = {
        "phc_health_facilities": "Health",
        "phc_education_facilities": "Education",
        "phc_water_facilities": "Water",
        "phc_markets": "Markets",
        "phc_government_offices": "Gov Offices",
        "airports": "Airports",
        "sea_ports": "Sea Ports",
    }

    for table_name in active_layers:
        rgb = _fac_rgb.get(table_name, [100, 100, 100])
        label = _fac_label.get(table_name, table_name)
        points = get_facility_points(tuple(sorted(affected)), table_name, limit=400)
        if not points:
            continue

        fac_data = []
        for pt in points:
            fac_data.append({
                "lat": pt["lat"],
                "lon": pt["lon"],
                "name": pt["name"],
                "district": pt.get("district", ""),
                "type": label,
                "color": rgb + [200],
                "radius": 80,
                "elevation": 500,
            })

        if fac_data:
            layers.append(pdk.Layer(
                "ColumnLayer",
                data=fac_data,
                get_position=["lon", "lat"],
                get_fill_color="color",
                get_elevation="elevation",
                elevation_scale=1,
                radius=80,
                disk_resolution=8,
                pickable=True,
                auto_highlight=True,
                highlight_color=[255, 255, 255, 120],
            ))

    # -- Flood risk hotspots as tall pillars --
    if show_hotspots and affected:
        hotspots = get_flood_risk_hotspots(tuple(sorted(affected)), limit=30)
        if hotspots:
            max_ead = max(h["ead"] for h in hotspots) if hotspots else 1
            hotspot_data = []
            for h in hotspots:
                # Scale pillar height by EAD (max ~20km)
                rel_ead = h["ead"] / max_ead if max_ead > 0 else 0.5
                pillar_height = 3000 + rel_ead * 17000

                # Color by depth: deeper = redder
                depth = min(h["depth"], 10)
                r = min(255, int(150 + depth * 10))
                g = max(0, int(80 - depth * 8))
                b = 0

                ead_text = (f"TZS {h['ead']/1e6:.2f}M" if h["ead"] >= 1e6
                            else f"TZS {h['ead']:,.0f}")
                hotspot_data.append({
                    "lat": h["lat"],
                    "lon": h["lon"],
                    "name": h["name"],
                    "district": h["district"],
                    "ead_text": ead_text,
                    "depth": h["depth"],
                    "damage": h["damage"],
                    "color": [r, g, b, 200],
                    "height": pillar_height,
                    "radius": 150,
                })

            layers.append(pdk.Layer(
                "ColumnLayer",
                data=hotspot_data,
                get_position=["lon", "lat"],
                get_fill_color="color",
                get_elevation="height",
                elevation_scale=1,
                radius=150,
                disk_resolution=12,
                pickable=True,
                auto_highlight=True,
                highlight_color=[255, 50, 50, 180],
            ))

    # -- Road network as 3D paths --
    if show_roads and affected:
        from .tcvmp_bridge import get_roads_in_districts
        roads = get_roads_in_districts(tuple(sorted(affected)))
        if roads:
            path_data = []
            road_colors = {
                "trunk": [230, 81, 0, 200],
                "primary": [245, 124, 0, 180],
                "trunk_link": [255, 183, 77, 150],
                "primary_link": [255, 224, 178, 130],
            }
            for road in roads:
                try:
                    geojson = json.loads(road["geojson"])
                    coords = geojson.get("coordinates", [])
                    if not coords:
                        continue
                    gtype = geojson.get("type", "")
                    if gtype == "MultiLineString":
                        for line in coords:
                            path_data.append({
                                "path": [[c[0], c[1]] for c in line],
                                "name": road["name"],
                                "type": road["type"],
                                "km": road["km"],
                                "color": road_colors.get(road["type"],
                                                         [150, 150, 150, 150]),
                                "width": 6 if road["type"] == "trunk" else 4,
                            })
                    else:
                        path_data.append({
                            "path": [[c[0], c[1]] for c in coords],
                            "name": road["name"],
                            "type": road["type"],
                            "km": road["km"],
                            "color": road_colors.get(road["type"],
                                                     [150, 150, 150, 150]),
                            "width": 6 if road["type"] == "trunk" else 4,
                        })
                except (json.JSONDecodeError, KeyError):
                    continue

            if path_data:
                layers.append(pdk.Layer(
                    "PathLayer",
                    data=path_data,
                    get_path="path",
                    get_color="color",
                    get_width="width",
                    width_scale=20,
                    width_min_pixels=2,
                    pickable=True,
                    auto_highlight=True,
                ))

    # -- Compute view center from alert districts --
    if district_alerts and geojson_data:
        alert_lats = []
        alert_lons = []
        for feature in geojson_data["features"]:
            name = feature["properties"]["display_name"]
            if name in district_alerts:
                for ring in _polygon_coords(feature["geometry"]):
                    for coord in ring:
                        alert_lons.append(coord[0])
                        alert_lats.append(coord[1])
        if alert_lats:
            center_lat = sum(alert_lats) / len(alert_lats)
            center_lon = sum(alert_lons) / len(alert_lons)
            zoom = 7
        else:
            center_lat, center_lon, zoom = -6.5, 35.0, 6
    else:
        center_lat, center_lon, zoom = -6.5, 35.0, 6

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
        pitch=45,
        bearing=-15,
    )

    tooltip = {
        "html": (
            "<b>{name}</b><br>"
            "<span style='font-size:11px;'>"
            "{agency} {level}<br>"
            "{detail}<br>"
            "{type} {district}<br>"
            "EAD: {ead_text}<br>"
            "Depth: {depth}m"
            "</span>"
        ),
        "style": {
            "backgroundColor": "rgba(0,0,0,0.8)",
            "color": "white",
            "fontSize": "12px",
            "padding": "6px 10px",
            "borderRadius": "4px",
        },
    }

    # Map provider/style selection
    _CARTO_MAP_STYLES = {
        "OpenStreetMap": pdk.map_styles.CARTO_ROAD,
        "Light": pdk.map_styles.CARTO_LIGHT,
        "Dark": pdk.map_styles.CARTO_DARK,
    }

    if base_map == "Satellite":
        # ESRI satellite raster tiles (no map_provider needed)
        satellite_tile = pdk.Layer(
            "TileLayer",
            data="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            min_zoom=0,
            max_zoom=19,
            tile_size=256,
            pickable=False,
        )
        deck = pdk.Deck(
            layers=[satellite_tile] + layers,
            initial_view_state=view_state,
            tooltip=tooltip,
            map_provider=None,
            height=620,
        )
    else:
        # CARTO vector tiles (free, no API key, no CORS issues)
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip,
            map_provider="carto",
            map_style=_CARTO_MAP_STYLES.get(base_map, pdk.map_styles.CARTO_ROAD),
            height=620,
        )

    return deck


# ═══════════════════════════════════════════════════════════════════
# KPI CARDS
# ═══════════════════════════════════════════════════════════════════

def _render_kpi_cards(district_alerts: dict, tcvmp_ok: bool):
    """Render top-level KPI summary cards."""
    all_districts = list(district_alerts.keys())
    n_districts = len(all_districts)

    # Count tiers
    tier_counts = {}
    agencies = set()
    for info in district_alerts.values():
        tier_counts[info["alert_level"]] = tier_counts.get(info["alert_level"], 0) + 1
        agencies.add(info["agency"])

    # Fetch data if TCVMP available
    pop_data = {}
    flood_totals = {}
    fac_summary = {}
    if tcvmp_ok and all_districts:
        pop_data = get_population_at_risk(tuple(sorted(all_districts)))
        flood_totals = get_flood_risk_totals(tuple(sorted(all_districts)))
        tiers = {}
        for dist, info in district_alerts.items():
            tier = info["alert_level"].lower()
            tiers.setdefault(tier, []).append(dist)
        fac_summary = get_exposure_summary(tiers)

    cols = st.columns(6)
    with cols[0]:
        _kpi_card("Districts Flagged", str(n_districts),
                  ", ".join(agencies) if agencies else "—", "#1a237e")
    with cols[1]:
        mw = tier_counts.get("MAJOR_WARNING", 0)
        w = tier_counts.get("WARNING", 0)
        a = tier_counts.get("ADVISORY", 0)
        _kpi_card("Alert Tiers", f"{mw} / {w} / {a}",
                  "Major / Warning / Advisory", "#b71c1c")
    with cols[2]:
        total_pop = pop_data.get("total_population", 0)
        if total_pop > 1_000_000:
            pop_str = f"{total_pop/1e6:.1f}M"
        elif total_pop > 1_000:
            pop_str = f"{total_pop/1e3:.0f}K"
        else:
            pop_str = str(total_pop) if total_pop else "—"
        _kpi_card("Population at Risk", pop_str,
                  f"{pop_data.get('total_settlements', 0)} settlements", "#1b5e20")
    with cols[3]:
        grand_total = fac_summary.get("grand_total", 0)
        _kpi_card("Facilities at Risk",
                  f"{grand_total:,}" if grand_total else "—",
                  "Health, Education, Water, Markets", "#e65100")
    with cols[4]:
        ead = flood_totals.get("total_ead_future", 0)
        if ead >= 1e6:
            ead_str = f"TZS {ead/1e6:.1f}M"
        elif ead > 0:
            ead_str = f"TZS {ead/1e3:.0f}K"
        else:
            ead_str = "—"
        _kpi_card("Flood EAD (Future)", ead_str,
                  f"{flood_totals.get('exposed_count', 0):,} exposed" if flood_totals else "—",
                  "#4a148c")
    with cols[5]:
        change = flood_totals.get("total_ead_change", 0)
        if change != 0:
            arrow = "+" if change > 0 else ""
            if abs(change) >= 1e6:
                chg_str = f"{arrow}{change/1e6:.1f}M"
            else:
                chg_str = f"{arrow}{change/1e3:.0f}K"
        else:
            chg_str = "—"
        _kpi_card("EAD Change", chg_str,
                  "Climate vs Baseline", "#bf360c" if change > 0 else "#2e7d32")


def _kpi_card(title: str, value: str, subtitle: str, color: str):
    """Render a single KPI metric card."""
    st.markdown(
        f'<div style="background:{color};color:white;padding:12px 14px;'
        f'border-radius:8px;text-align:center;min-height:90px;">'
        f'<div style="font-size:11px;opacity:0.85;text-transform:uppercase;'
        f'letter-spacing:0.5px;">{title}</div>'
        f'<div style="font-size:22px;font-weight:bold;margin:4px 0;">{value}</div>'
        f'<div style="font-size:10px;opacity:0.75;">{subtitle}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════
# QUICK ANALYSIS PANEL (right sidebar)
# ═══════════════════════════════════════════════════════════════════

def _render_quick_analysis(district_alerts: dict):
    """Compact right-panel analysis: alert breakdown + top districts."""
    if not district_alerts:
        st.caption("No agency alerts to analyse.")
        return

    # Hazard type breakdown with icons
    hazard_types = {}
    for dist, info in district_alerts.items():
        ht = info.get("hazard_type", "")
        if ht:
            hazard_types.setdefault(ht, []).append(dist)

    if hazard_types:
        st.markdown(
            '<div style="font-size:11px;font-weight:bold;margin-bottom:4px;">'
            'Active Hazards</div>',
            unsafe_allow_html=True,
        )
        for ht, dists in hazard_types.items():
            icon_uri = _hazard_icon_b64(ht, size=64)
            label = _HAZARD_LABELS.get(ht, ht)
            icon_html = (
                f'<img src="{icon_uri}" style="width:20px;height:20px;'
                f'margin-right:4px;vertical-align:middle;"/>'
                if icon_uri else ""
            )
            st.markdown(
                f'<div style="display:flex;align-items:center;'
                f'padding:3px 6px;margin:2px 0;background:#f5f5f5;'
                f'border-radius:4px;border:1px solid #e0e0e0;">'
                f'{icon_html}'
                f'<span style="font-size:11px;font-weight:600;">'
                f'{label}</span>'
                f'<span style="margin-left:auto;font-size:10px;color:#666;">'
                f'{len(dists)} dist.</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("")

    # Alert breakdown by agency
    by_agency = {}
    for dist, info in district_alerts.items():
        agency = info["agency"]
        by_agency.setdefault(agency, []).append(dist)

    for agency, dists in by_agency.items():
        color = "#4CAF50" if agency == "TMA" else "#2196F3"
        st.markdown(
            f'<div style="border-left:3px solid {color};padding:4px 8px;'
            f'margin:4px 0;font-size:12px;">'
            f'<b>{agency}</b>: {len(dists)} districts</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Top affected districts by alert severity
    sorted_dists = sorted(
        district_alerts.items(),
        key=lambda x: _ALERT_RANK.get(x[1]["alert_level"], 0),
        reverse=True,
    )

    st.markdown(
        '<div style="font-size:12px;font-weight:bold;margin-bottom:4px;">'
        'Top Affected Districts</div>',
        unsafe_allow_html=True,
    )

    for dist, info in sorted_dists[:12]:
        level = info["alert_level"]
        color = _ALERT_COLORS.get(level, "#EEE")
        tc = "#FFF" if level != "ADVISORY" else "#000"
        ht = info.get("hazard_type", "")
        icon_uri = _hazard_icon_b64(ht, size=64)
        # Invert icon for dark backgrounds (MAJOR_WARNING, WARNING)
        icon_filter = "filter:invert(1);" if level != "ADVISORY" else ""
        icon_html = (
            f'<img src="{icon_uri}" style="width:16px;height:16px;'
            f'margin-right:4px;vertical-align:middle;{icon_filter}"/>'
            if icon_uri else ""
        )
        st.markdown(
            f'<div style="background:{color};color:{tc};padding:3px 8px;'
            f'border-radius:3px;margin:2px 0;font-size:11px;'
            f'display:flex;align-items:center;">'
            f'{icon_html}'
            f'<b>{dist}</b>&nbsp;'
            f'<span style="opacity:0.8;margin-left:auto;">({info["agency"]})</span></div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════
# DETAILED ANALYSIS TABS (full-width below map)
# ═══════════════════════════════════════════════════════════════════

def _render_infrastructure_tab(district_alerts: dict):
    """Tab 1: Infrastructure exposure with Plotly charts."""
    all_districts = list(district_alerts.keys())
    if not all_districts:
        st.info("No districts to analyse.")
        return

    tiers = {}
    for dist, info in district_alerts.items():
        tier = info["alert_level"].lower()
        tiers.setdefault(tier, []).append(dist)

    summary = get_exposure_summary(tiers)
    if not summary or summary.get("grand_total", 0) == 0:
        st.info("No facility data available for affected districts.")
        return

    # -- Overview metrics --
    col1, col2 = st.columns([2, 3])

    with col1:
        st.markdown("##### Exposure by Alert Tier")
        for tier_key in ["major_warning", "warning", "advisory"]:
            td = summary.get(tier_key)
            if not td or td["total_facilities"] == 0:
                continue
            bg = _ALERT_COLORS.get(tier_key.upper(), "#EEE")
            tc = "#FFF" if tier_key != "advisory" else "#000"
            st.markdown(
                f'<div style="background:{bg};color:{tc};padding:8px 12px;'
                f'border-radius:6px;margin:4px 0;font-size:13px;">'
                f'<b>{_ALERT_LABEL.get(tier_key.upper(), tier_key)}</b>: '
                f'{td["total_facilities"]:,} facilities in '
                f'{len(td["districts"])} districts</div>',
                unsafe_allow_html=True,
            )

            # Type breakdown
            for ftype, count in sorted(
                td.get("by_type", {}).items(), key=lambda x: -x[1]
            ):
                if count > 0:
                    st.caption(f"  {ftype}: {count:,}")

    with col2:
        # Plotly chart: facility counts by type and tier
        try:
            import plotly.graph_objects as go

            tier_labels = []
            tier_data = {}

            for tier_key in ["major_warning", "warning", "advisory"]:
                td = summary.get(tier_key)
                if not td or td["total_facilities"] == 0:
                    continue
                tier_label = _ALERT_LABEL.get(tier_key.upper(), tier_key)
                tier_labels.append(tier_label)
                for ftype, count in td.get("by_type", {}).items():
                    tier_data.setdefault(ftype, []).append(count)

            if tier_labels and tier_data:
                fig = go.Figure()
                colors = ["#E53935", "#1E88E5", "#00ACC1", "#F57C00",
                          "#5E35B1", "#6D4C41", "#0277BD"]
                for i, (ftype, counts) in enumerate(tier_data.items()):
                    # Pad counts if not present in all tiers
                    while len(counts) < len(tier_labels):
                        counts.append(0)
                    fig.add_trace(go.Bar(
                        name=ftype, x=tier_labels, y=counts,
                        marker_color=colors[i % len(colors)],
                    ))
                fig.update_layout(
                    barmode="stack",
                    title="Facilities at Risk by Tier & Type",
                    height=350,
                    margin=dict(l=40, r=20, t=40, b=40),
                    legend=dict(orientation="h", y=-0.15),
                    font=dict(size=11),
                )
                st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            pass

    # -- Education & Water type breakdown --
    st.markdown("---")
    edu_col, water_col = st.columns(2)

    with edu_col:
        st.markdown("##### Education Facility Types")
        edu_types = get_education_type_breakdown(tuple(sorted(all_districts)))
        if edu_types:
            try:
                import plotly.graph_objects as go
                labels = [e["type"] for e in edu_types[:8]]
                values = [e["count"] for e in edu_types[:8]]
                fig = go.Figure(data=[go.Pie(
                    labels=labels, values=values, hole=0.4,
                    marker_colors=["#1565C0", "#42A5F5", "#90CAF9",
                                   "#BBDEFB", "#1E88E5", "#64B5F6",
                                   "#2196F3", "#E3F2FD"],
                )])
                fig.update_layout(
                    title=f"Schools ({sum(values):,} total)",
                    height=300,
                    margin=dict(l=20, r=20, t=40, b=20),
                    legend=dict(font=dict(size=9)),
                    font=dict(size=11),
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                for e in edu_types[:8]:
                    st.caption(f"  {e['type']}: {e['count']:,}")
        else:
            st.caption("No education data.")

    with water_col:
        st.markdown("##### Water Source Types")
        water_types = get_water_type_breakdown(tuple(sorted(all_districts)))
        if water_types:
            try:
                import plotly.graph_objects as go
                labels = [w["type"] for w in water_types[:8]]
                values = [w["count"] for w in water_types[:8]]
                # Color-code: protected=blue, unprotected=red
                colors = []
                for l in labels:
                    if "Unprotected" in l:
                        colors.append("#EF5350")
                    elif "Protected" in l or "Tap" in l or "Tube" in l:
                        colors.append("#42A5F5")
                    elif "Rain" in l:
                        colors.append("#66BB6A")
                    elif "Dam" in l:
                        colors.append("#FFA726")
                    else:
                        colors.append("#78909C")

                fig = go.Figure(data=[go.Pie(
                    labels=labels, values=values, hole=0.4,
                    marker_colors=colors,
                )])
                fig.update_layout(
                    title=f"Water Points ({sum(values):,} total)",
                    height=300,
                    margin=dict(l=20, r=20, t=40, b=20),
                    legend=dict(font=dict(size=9)),
                    font=dict(size=11),
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                for w in water_types[:8]:
                    st.caption(f"  {w['type']}: {w['count']:,}")
        else:
            st.caption("No water data.")


def _render_flood_risk_tab(district_alerts: dict):
    """Tab 2: Flood risk analysis with charts."""
    all_districts = list(district_alerts.keys())
    if not all_districts:
        st.info("No districts to analyse.")
        return

    sorted_dists = tuple(sorted(all_districts))

    # Summary totals
    totals = get_flood_risk_totals(sorted_dists)
    if not totals or totals.get("total_facilities", 0) == 0:
        st.info("No flood risk data available for affected districts.")
        return

    # Metrics row
    mcols = st.columns(5)
    with mcols[0]:
        st.metric("Facilities Assessed", f"{totals['total_facilities']:,}")
    with mcols[1]:
        st.metric("Exposed (RP100)", f"{totals['exposed_count']:,}")
    with mcols[2]:
        ead_f = totals.get("total_ead_future", 0)
        st.metric("EAD Future",
                   f"TZS {ead_f/1e6:.1f}M" if ead_f >= 1e6 else f"TZS {ead_f:,.0f}")
    with mcols[3]:
        ead_b = totals.get("total_ead_baseline", 0)
        st.metric("EAD Baseline",
                   f"TZS {ead_b/1e6:.1f}M" if ead_b >= 1e6 else f"TZS {ead_b:,.0f}")
    with mcols[4]:
        change = totals.get("total_ead_change", 0)
        arrow = "+" if change > 0 else ""
        delta_str = (f"{arrow}TZS {change/1e6:.1f}M" if abs(change) >= 1e6
                     else f"{arrow}TZS {change:,.0f}")
        st.metric("Climate Change Impact", delta_str)

    st.markdown("---")

    chart_col, depth_col = st.columns(2)

    with chart_col:
        # EAD by district (baseline vs future)
        st.markdown("##### Expected Annual Damage by District")
        ead_data = get_flood_ead_by_district(sorted_dists)
        if ead_data:
            try:
                import plotly.graph_objects as go
                districts = [d["district"] for d in ead_data]
                baseline = [d["ead_baseline"] for d in ead_data]
                future = [d["ead_future"] for d in ead_data]

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name="Baseline", x=districts, y=baseline,
                    marker_color="#5C6BC0",
                ))
                fig.add_trace(go.Bar(
                    name="Future (SSP)", x=districts, y=future,
                    marker_color="#EF5350",
                ))
                fig.update_layout(
                    barmode="group",
                    height=380,
                    margin=dict(l=40, r=20, t=10, b=80),
                    yaxis_title="EAD (TZS)",
                    legend=dict(orientation="h", y=1.02),
                    font=dict(size=10),
                    xaxis_tickangle=-45,
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                for d in ead_data:
                    st.caption(
                        f"**{d['district']}**: Baseline {d['ead_baseline']:,.0f} "
                        f"/ Future {d['ead_future']:,.0f}"
                    )
        else:
            st.caption("No EAD data.")

    with depth_col:
        # Flood depth distribution
        st.markdown("##### Flood Depth Distribution (RP100)")
        depth_dist = get_flood_depth_distribution(sorted_dists)
        if depth_dist:
            try:
                import plotly.graph_objects as go
                ranges = [d["range"] for d in depth_dist]
                counts = [d["count"] for d in depth_dist]
                colors_map = {
                    "No flood": "#E8EAF6",
                    "0-0.3m": "#C5CAE9",
                    "0.3-1m": "#FFF176",
                    "1-3m": "#FFB74D",
                    "3-6m": "#FF7043",
                    ">6m": "#D32F2F",
                }
                colors = [colors_map.get(r, "#90A4AE") for r in ranges]

                fig = go.Figure(data=[go.Bar(
                    x=ranges, y=counts, marker_color=colors,
                    text=[f"{c:,}" for c in counts],
                    textposition="outside",
                )])
                fig.update_layout(
                    height=380,
                    margin=dict(l=40, r=20, t=10, b=40),
                    yaxis_title="Number of Facilities",
                    xaxis_title="Flood Depth Range",
                    font=dict(size=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                for d in depth_dist:
                    st.caption(f"  {d['range']}: {d['count']:,}")
        else:
            st.caption("No depth data.")

    # Top risk facilities table
    st.markdown("---")
    st.markdown("##### Top Risk Facilities")
    top_fac = get_flood_risk_facilities(sorted_dists, limit=15)
    if top_fac:
        try:
            import plotly.graph_objects as go
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=["Facility", "District", "EAD Future", "EAD Baseline",
                            "Depth (m)", "Change %"],
                    fill_color="#1a237e",
                    font=dict(color="white", size=11),
                    align="left",
                ),
                cells=dict(
                    values=[
                        [f["name"][:30] for f in top_fac],
                        [f["district"] for f in top_fac],
                        [f"TZS {f['ead_future']:,.0f}" for f in top_fac],
                        [f"TZS {f['ead_baseline']:,.0f}" for f in top_fac],
                        [f"{f['depth_f_rp100']:.2f}" for f in top_fac],
                        [f"{f['ead_change_pct']:+.0f}%" if f["ead_change_pct"] else "—"
                         for f in top_fac],
                    ],
                    fill_color=[
                        ["#FFEBEE" if f["ead_future"] > 10000 else "#FFF3E0"
                         if f["ead_future"] > 1000 else "white"
                         for f in top_fac]
                    ],
                    font=dict(size=10),
                    align="left",
                ),
            )])
            fig.update_layout(
                height=min(400, 50 + len(top_fac) * 25),
                margin=dict(l=0, r=0, t=0, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            for f in top_fac:
                st.caption(
                    f"**{f['name']}** ({f['district']}) — "
                    f"EAD: TZS {f['ead_future']:,.0f}, Depth: {f['depth_f_rp100']:.2f}m"
                )
    else:
        st.caption("No facility-level risk data.")


def _render_climate_tab(district_alerts: dict):
    """Tab 3: Climate exposure indicators."""
    all_districts = list(district_alerts.keys())
    if not all_districts:
        st.info("No districts to analyse.")
        return

    sorted_dists = tuple(sorted(all_districts))
    indicators = get_climate_indicators_for_districts(sorted_dists)

    if not indicators:
        st.info("No climate indicator data available for affected districts.")
        return

    # Group by indicator type
    _cat_groups = {
        "Temperature": [],
        "Precipitation": [],
        "Risk Indices": [],
    }
    for ind in indicators:
        name = ind["indicator"].lower()
        if "tas" in name or "temp" in name or "hot" in name or "cold" in name or "warm" in name or "tropical" in name:
            _cat_groups["Temperature"].append(ind)
        elif "pr" in name or "rain" in name or "wet" in name or "dry" in name or "spei" in name or "precip" in name:
            _cat_groups["Precipitation"].append(ind)
        else:
            _cat_groups["Risk Indices"].append(ind)

    for group_name, group_inds in _cat_groups.items():
        if not group_inds:
            continue

        st.markdown(f"##### {group_name}")

        try:
            import plotly.graph_objects as go

            fig = go.Figure()
            ind_names = [f"{i['indicator']} ({i['scenario']})" for i in group_inds]
            exposure_pcts = [i["exposure_pct"] for i in group_inds]

            # Color by exposure severity
            colors = []
            for pct in exposure_pcts:
                if pct >= 80:
                    colors.append("#D32F2F")
                elif pct >= 50:
                    colors.append("#F57C00")
                elif pct >= 20:
                    colors.append("#FDD835")
                else:
                    colors.append("#66BB6A")

            fig.add_trace(go.Bar(
                y=ind_names, x=exposure_pcts,
                orientation="h",
                marker_color=colors,
                text=[f"{p:.0f}%" for p in exposure_pcts],
                textposition="outside",
            ))
            fig.update_layout(
                height=max(200, len(group_inds) * 40 + 60),
                margin=dict(l=200, r=40, t=10, b=20),
                xaxis_title="Exposure %",
                xaxis=dict(range=[0, 110]),
                font=dict(size=10),
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            pass

        # Detail table
        for ind in group_inds:
            exp_color = ("#D32F2F" if ind["exposure_pct"] >= 80
                         else "#F57C00" if ind["exposure_pct"] >= 50
                         else "#FDD835" if ind["exposure_pct"] >= 20
                         else "#66BB6A")
            st.markdown(
                f'<div style="border-left:4px solid {exp_color};padding:4px 10px;'
                f'margin:3px 0;font-size:11px;">'
                f'<b>{ind["indicator"]}</b> ({ind["scenario"]}, {ind["timeslice"]}) — '
                f'{ind["total_exposed"]:,}/{ind["total_features"]:,} exposed '
                f'({ind["exposure_pct"]:.0f}%) — '
                f'Range: [{ind["value_min"]:.2f}, {ind["value_max"]:.2f}] {ind["unit"]}, '
                f'Mean: {ind["value_mean"]:.2f} — '
                f'{ind["n_districts"]} districts</div>',
                unsafe_allow_html=True,
            )

        st.markdown("")


def _render_transport_tab(district_alerts: dict):
    """Tab 4: Transport & roads analysis."""
    all_districts = list(district_alerts.keys())
    if not all_districts:
        st.info("No districts to analyse.")
        return

    sorted_dists = tuple(sorted(all_districts))

    road_col, rail_col = st.columns(2)

    with road_col:
        st.markdown("##### Road Network at Risk")
        road_km = get_road_km_summary(sorted_dists)
        if road_km:
            total_km = sum(v["km"] for v in road_km.values())
            total_seg = sum(v["segments"] for v in road_km.values())

            st.metric("Total Road Length", f"{total_km:.0f} km")
            st.metric("Road Segments", f"{total_seg:,}")

            try:
                import plotly.graph_objects as go
                types = list(road_km.keys())
                kms = [road_km[t]["km"] for t in types]
                segs = [road_km[t]["segments"] for t in types]
                colors = {"trunk": "#E65100", "primary": "#F57C00",
                          "trunk_link": "#FFB74D", "primary_link": "#FFE0B2"}

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=types, y=kms,
                    marker_color=[colors.get(t, "#999") for t in types],
                    text=[f"{k:.0f} km" for k in kms],
                    textposition="outside",
                ))
                fig.update_layout(
                    height=300,
                    margin=dict(l=40, r=20, t=10, b=40),
                    yaxis_title="Length (km)",
                    font=dict(size=11),
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                for rtype, data in road_km.items():
                    st.caption(f"  {rtype}: {data['km']:.1f} km ({data['segments']} segments)")
        else:
            st.caption("No road data available.")

    with rail_col:
        st.markdown("##### Railway Network at Risk")
        rail = get_railway_summary(sorted_dists)
        if rail and rail.get("km", 0) > 0:
            st.metric("Railway Length", f"{rail['km']:.0f} km")
            st.metric("Railway Segments", f"{rail['segments']:,}")

            try:
                import plotly.graph_objects as go
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=rail["km"],
                    title={"text": "Railway km in Hazard Zone"},
                    gauge={
                        "axis": {"range": [0, max(500, rail["km"] * 1.5)]},
                        "bar": {"color": "#1a237e"},
                        "steps": [
                            {"range": [0, 100], "color": "#C8E6C9"},
                            {"range": [100, 250], "color": "#FFF9C4"},
                            {"range": [250, 500], "color": "#FFCDD2"},
                        ],
                    },
                ))
                fig.update_layout(
                    height=250,
                    margin=dict(l=20, r=20, t=40, b=20),
                    font=dict(size=11),
                )
                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                pass
        else:
            st.caption("No railway data in affected area.")

    # Population at risk detail
    st.markdown("---")
    st.markdown("##### Population at Risk — District Breakdown")
    pop_data = get_population_at_risk(sorted_dists)
    if pop_data and pop_data.get("by_district"):
        by_dist = pop_data["by_district"]
        try:
            import plotly.graph_objects as go
            sorted_pop = sorted(by_dist.items(), key=lambda x: -x[1]["population"])[:20]
            dist_names = [d[0] for d in sorted_pop]
            pops = [d[1]["population"] for d in sorted_pop]
            settlements = [d[1]["settlements"] for d in sorted_pop]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=dist_names, x=pops,
                orientation="h",
                marker_color="#1a237e",
                text=[f"{p:,}" for p in pops],
                textposition="outside",
                name="Population",
            ))
            fig.update_layout(
                height=max(300, len(dist_names) * 25 + 60),
                margin=dict(l=120, r=80, t=10, b=20),
                xaxis_title="Population",
                font=dict(size=10),
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            for dist, data in sorted(
                by_dist.items(), key=lambda x: -x[1]["population"]
            )[:15]:
                st.caption(
                    f"  **{dist}**: {data['population']:,} "
                    f"({data['settlements']} settlements)"
                )
    else:
        st.caption("No population data available.")


# ═══════════════════════════════════════════════════════════════════
# MAIN PAGE RENDERER
# ═══════════════════════════════════════════════════════════════════

def render_tcvmp_page(issue_date: date = None):
    """Render the full TCVMP analysis page.

    Called from dmd_page.py as Step 1 of the analysis workflow.
    """
    if issue_date is None:
        issue_date = date.today()

    tcvmp_ok = is_tcvmp_available()

    # -- Header --
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1a237e,#283593);'
        'color:white;padding:12px 18px;border-radius:8px;margin-bottom:12px;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.15);">'
        '<b style="font-size:16px;">TCVMP Analysis</b>'
        '<span style="font-size:11px;margin-left:12px;opacity:0.85;">'
        'Tanzania Climate Vulnerability Maps &mdash; Agency Hazard Overlay '
        '&bull; Infrastructure Exposure &bull; Flood Risk &bull; Climate Indicators'
        '</span></div>',
        unsafe_allow_html=True,
    )

    if not tcvmp_ok:
        st.warning("TCVMP database offline. Infrastructure and risk data unavailable.")

    # -- Build agency alerts for all 3 days --
    day_alerts = _build_agency_alerts(issue_date)

    has_alerts = any(bool(alerts) for alerts in day_alerts.values())
    if not has_alerts:
        st.info(
            "No agency data available yet. "
            "TMA and MoW need to push their assessments first. "
            "The map will show infrastructure layers without hazard overlay."
        )

    # -- Day selector --
    day_labels = [
        f"Day {d+1} — {(issue_date + timedelta(days=d)).strftime('%a %d %b')}"
        for d in range(3)
    ]
    selected_day = st.radio(
        "Forecast Day", day_labels, horizontal=True, key="tcvmp_day"
    )
    day_idx = day_labels.index(selected_day)
    district_alerts = day_alerts.get(day_idx, {})

    # -- Alert summary bar with hazard icons --
    if district_alerts:
        tier_counts = {}
        hazard_counts = {}
        for info in district_alerts.values():
            tier_counts[info["alert_level"]] = (
                tier_counts.get(info["alert_level"], 0) + 1
            )
            ht = info.get("hazard_type", "")
            if ht:
                hazard_counts[ht] = hazard_counts.get(ht, 0) + 1

        # Alert level badges
        level_parts = []
        for level in ["MAJOR_WARNING", "WARNING", "ADVISORY"]:
            if tier_counts.get(level, 0) > 0:
                level_parts.append(
                    f'<span style="background:{_ALERT_COLORS[level]};'
                    f'color:{"#FFF" if level != "ADVISORY" else "#000"};'
                    f'padding:2px 8px;border-radius:3px;font-size:12px;'
                    f'margin-right:6px;">'
                    f'{_ALERT_LABEL[level]}: {tier_counts[level]}</span>'
                )

        # Hazard type icons
        hazard_parts = []
        for ht, count in hazard_counts.items():
            icon_uri = _hazard_icon_b64(ht, size=64)
            label = _HAZARD_LABELS.get(ht, ht)
            if icon_uri:
                hazard_parts.append(
                    f'<span style="display:inline-flex;align-items:center;'
                    f'margin-right:10px;background:#f5f5f5;padding:3px 8px;'
                    f'border-radius:5px;border:1px solid #ddd;">'
                    f'<img src="{icon_uri}" style="width:22px;height:22px;'
                    f'margin-right:5px;"/>'
                    f'<span style="font-size:11px;font-weight:600;">'
                    f'{label} ({count})</span></span>'
                )

        agencies = set(info["agency"] for info in district_alerts.values())
        st.markdown(
            f'<div style="padding:6px 0;font-size:13px;">'
            f'<b>{len(district_alerts)}</b> districts flagged by '
            f'<b>{", ".join(agencies)}</b> &mdash; '
            f'{"".join(level_parts)}'
            f'</div>',
            unsafe_allow_html=True,
        )
        if hazard_parts:
            st.markdown(
                f'<div style="padding:2px 0 6px 0;">'
                f'{"".join(hazard_parts)}</div>',
                unsafe_allow_html=True,
            )

    # -- KPI Cards --
    if district_alerts and tcvmp_ok:
        _render_kpi_cards(district_alerts, tcvmp_ok)
        st.markdown("")

    # -- View mode selector --
    _vm_cols = st.columns([4, 2, 1])
    with _vm_cols[1]:
        view_mode = st.radio(
            "View",
            ["Single", "Compare", "Fullscreen"],
            horizontal=True,
            key="tcvmp_view_mode",
            label_visibility="collapsed",
        )
    with _vm_cols[2]:
        if view_mode == "Compare":
            panel_layout = st.radio(
                "Panels", ["2", "4", "6"], horizontal=True,
                key="tcvmp_panel_count", label_visibility="collapsed",
            )
        else:
            panel_layout = "1"

    # ================================================================
    # COMPARE MODE — multi-panel fullscreen comparison
    # ================================================================
    if view_mode == "Compare":
        n_panels = int(panel_layout)

        # Fullscreen CSS — hide chrome for maximum space
        st.markdown(
            """
            <style>
            [data-testid="stSidebar"] { display: none !important; }
            header[data-testid="stHeader"] { display: none !important; }
            [data-testid="stToolbar"] { display: none !important; }
            footer { display: none !important; }
            #MainMenu { display: none !important; }
            .stDeployButton { display: none !important; }
            .stMainBlockContainer,
            [data-testid="stAppViewBlockContainer"] {
                padding-top: 0.5rem !important;
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
                max-width: 100% !important;
            }
            section[data-testid="stMain"] { padding: 0 !important; }
            /* Tighter spacing inside panels */
            .cmp-panel {
                background: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 4px 6px;
                margin-bottom: 4px;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        _day_labels_cmp = [
            f"Day {d+1} — {(issue_date + timedelta(days=d)).strftime('%a %d %b')}"
            for d in range(3)
        ]
        _level_options_cmp = ["Major Warning", "Warning", "Advisory"]
        _level_map_cmp = {
            "Major Warning": "MAJOR_WARNING",
            "Warning": "WARNING",
            "Advisory": "ADVISORY",
        }

        # Panel heights based on count
        _panel_heights = {2: 520, 4: 380, 6: 340}
        _p_height = _panel_heights.get(n_panels, 400)

        # Use @st.fragment so each panel re-renders independently
        @st.fragment
        def _render_comparison_panel(pid: int):
            """Render one independent map panel with its own controls."""
            st.markdown(
                f'<div class="cmp-panel">'
                f'<b style="font-size:12px;">Panel {pid + 1}</b></div>',
                unsafe_allow_html=True,
            )
            # Compact controls row
            r1, r2, r3 = st.columns([1.5, 1, 1.5])
            with r1:
                p_day = st.selectbox(
                    "Day", _day_labels_cmp,
                    index=min(pid, 2),
                    key=f"cmp_day_{pid}",
                    label_visibility="collapsed",
                )
            with r2:
                p_levels = st.multiselect(
                    "Levels", _level_options_cmp,
                    default=_level_options_cmp,
                    key=f"cmp_levels_{pid}",
                    label_visibility="collapsed",
                )
            with r3:
                _base_opts = ["OSM", "Sat", "Light", "Dark"]
                p_base = st.radio(
                    "Base", _base_opts,
                    index=1, horizontal=True,
                    key=f"cmp_base_{pid}",
                    label_visibility="collapsed",
                )

            p_hotspots = st.checkbox(
                "Flood Hotspots", value=False, key=f"cmp_hs_{pid}",
            )

            _base_name_map = {
                "OSM": "OpenStreetMap", "Sat": "Satellite",
                "Light": "Light", "Dark": "Dark",
            }
            p_base_full = _base_name_map.get(p_base, "Satellite")

            p_day_idx = _day_labels_cmp.index(p_day)
            p_alerts = day_alerts.get(p_day_idx, {})

            # Filter alerts by selected levels
            active_lvls = [_level_map_cmp[l] for l in p_levels]
            if p_alerts and active_lvls:
                alerts_map = {
                    d: info for d, info in p_alerts.items()
                    if info["alert_level"] in active_lvls
                }
            else:
                alerts_map = {}

            # Render lightweight HTML map (no st_folium overhead)
            map_html = _build_compare_map(
                alerts_map,
                base_map=p_base_full,
                show_hotspots=p_hotspots,
            )
            st_html.html(map_html, height=_p_height, scrolling=False)

            # -- Exposure data below map --
            affected = list(alerts_map.keys())
            if not affected:
                st.caption("No districts selected — choose alert levels above")
                return

            # Alert tier badges
            tier_c = {}
            for info in alerts_map.values():
                tier_c[info["alert_level"]] = (
                    tier_c.get(info["alert_level"], 0) + 1
                )
            badge_parts = []
            for lv in ["MAJOR_WARNING", "WARNING", "ADVISORY"]:
                if tier_c.get(lv, 0) > 0:
                    badge_parts.append(
                        f'<span style="background:{_ALERT_COLORS[lv]};'
                        f'color:{"#FFF" if lv != "ADVISORY" else "#000"};'
                        f'padding:1px 5px;border-radius:3px;'
                        f'font-size:10px;margin-right:3px;">'
                        f'{tier_c[lv]}</span>'
                    )
            st.markdown(
                f'<div style="font-size:11px;padding:2px 0;">'
                f'<b>{len(alerts_map)}</b> districts '
                f'{"".join(badge_parts)}</div>',
                unsafe_allow_html=True,
            )

            # -- Exposure metrics in compact cards --
            aff_tuple = tuple(sorted(affected))

            # Population
            pop_data = get_population_at_risk(aff_tuple)
            total_pop = pop_data.get("total_population", 0)
            settlements = pop_data.get("total_settlements", 0)

            # Facilities
            fac_counts = get_district_facility_counts(
                aff_tuple,
                layers=("phc_health_facilities", "phc_education_facilities",
                        "phc_water_facilities"),
            )
            health_n = sum(fac_counts.get("phc_health_facilities", {}).values())
            edu_n = sum(fac_counts.get("phc_education_facilities", {}).values())
            water_n = sum(fac_counts.get("phc_water_facilities", {}).values())

            # Flood risk
            flood_totals = get_flood_risk_totals(aff_tuple)
            ead_base = flood_totals.get("total_ead_baseline", 0)
            ead_future = flood_totals.get("total_ead_future", 0)
            flood_exposed = flood_totals.get("exposed_count", 0)

            # Roads
            road_summary = get_road_km_summary(aff_tuple)
            total_road_km = sum(v["km"] for v in road_summary.values())

            # Compact metric cards
            _card_css = (
                "font-size:11px;padding:3px 6px;border-radius:4px;"
                "border:1px solid #e0e0e0;margin:2px 0;background:#fff;"
            )
            _val_css = "font-weight:700;font-size:13px;color:#1a237e;"

            m1, m2 = st.columns(2)
            with m1:
                st.markdown(
                    f'<div style="{_card_css}">'
                    f'<span style="{_val_css}">'
                    f'{total_pop:,}</span><br>'
                    f'Population at risk<br>'
                    f'<span style="color:#666;">{settlements} settlements</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="{_card_css}">'
                    f'<span style="{_val_css}">{health_n}</span> Health &nbsp;'
                    f'<span style="{_val_css}">{edu_n}</span> Edu &nbsp;'
                    f'<span style="{_val_css}">{water_n}</span> Water'
                    f'<br>Facilities exposed</div>',
                    unsafe_allow_html=True,
                )
            with m2:
                ead_disp = (
                    f"TZS {ead_future/1e9:.1f}B" if ead_future >= 1e9
                    else f"TZS {ead_future/1e6:.1f}M" if ead_future >= 1e6
                    else f"TZS {ead_future:,.0f}"
                )
                ead_change = ead_future - ead_base
                change_pct = (
                    f"+{ead_change / ead_base * 100:.0f}%"
                    if ead_base > 0 else "—"
                )
                st.markdown(
                    f'<div style="{_card_css}">'
                    f'<span style="{_val_css}">{ead_disp}</span><br>'
                    f'EAD (future) &nbsp;'
                    f'<span style="color:{"#c62828" if ead_change > 0 else "#2e7d32"};'
                    f'font-size:11px;">{change_pct}</span><br>'
                    f'<span style="color:#666;">{flood_exposed} flood-exposed</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="{_card_css}">'
                    f'<span style="{_val_css}">{total_road_km:.0f} km</span><br>'
                    f'Road network at risk</div>',
                    unsafe_allow_html=True,
                )

            # Climate indicators (compact)
            climate = get_climate_indicators_for_districts(aff_tuple)
            if climate:
                clim_parts = []
                for ci in climate[:4]:
                    exp_pct = ci.get("exposure_pct", 0)
                    clim_parts.append(
                        f'<span style="display:inline-block;margin:1px 3px;'
                        f'padding:1px 5px;border-radius:3px;font-size:10px;'
                        f'background:{"#ffcdd2" if exp_pct > 50 else "#fff9c4" if exp_pct > 20 else "#c8e6c9"};'
                        f'border:1px solid #ddd;">'
                        f'{ci["indicator"]}: {exp_pct:.0f}%</span>'
                    )
                st.markdown(
                    f'<div style="padding:2px 0;font-size:10px;color:#555;">'
                    f'Climate exposure: {"".join(clim_parts)}</div>',
                    unsafe_allow_html=True,
                )

        # Render panels in grid: 2-col for 2/4, 3-col for 6
        cols_per_row = 3 if n_panels == 6 else 2
        n_rows = math.ceil(n_panels / cols_per_row)
        pid = 0
        for _row_i in range(n_rows):
            row_cols = st.columns(cols_per_row, gap="small")
            for col_i in range(cols_per_row):
                if pid < n_panels:
                    with row_cols[col_i]:
                        _render_comparison_panel(pid)
                    pid += 1

        # Collapsible analysis below
        if tcvmp_ok and district_alerts:
            with st.expander("Detailed Analysis", expanded=False):
                atabs = st.tabs([
                    "Infrastructure Exposure",
                    "Flood Risk Assessment",
                    "Climate Indicators",
                    "Transport & Population",
                ])
                with atabs[0]:
                    _render_infrastructure_tab(district_alerts)
                with atabs[1]:
                    _render_flood_risk_tab(district_alerts)
                with atabs[2]:
                    _render_climate_tab(district_alerts)
                with atabs[3]:
                    _render_transport_tab(district_alerts)
        return

    # ================================================================
    # FULLSCREEN MODE
    # ================================================================
    if view_mode == "Fullscreen":
        # Inject CSS to hide sidebar, header, footer and make content fill viewport
        st.markdown(
            """
            <style>
            /* Hide Streamlit chrome */
            [data-testid="stSidebar"] { display: none !important; }
            header[data-testid="stHeader"] { display: none !important; }
            [data-testid="stToolbar"] { display: none !important; }
            footer { display: none !important; }
            #MainMenu { display: none !important; }
            .stDeployButton { display: none !important; }

            /* Remove all padding/margin from main content */
            .stMainBlockContainer,
            [data-testid="stAppViewBlockContainer"] {
                padding-top: 0.5rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                max-width: 100% !important;
            }
            section[data-testid="stMain"] {
                padding: 0 !important;
            }

            /* Floating control panel style */
            .fs-controls {
                background: rgba(255,255,255,0.95);
                border-radius: 8px;
                padding: 8px 14px;
                box-shadow: 0 2px 12px rgba(0,0,0,0.15);
                margin-bottom: 6px;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Compact control bar
        st.markdown(
            '<div class="fs-controls">'
            '<span style="font-weight:600;font-size:13px;">Map Controls</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        ctrl_cols = st.columns([1.2, 1.5, 2.5, 1.2, 1.6])
        with ctrl_cols[0]:
            show_hazard = st.checkbox(
                "Agency Alerts", value=True, key="tcvmp_lyr_hazard"
            )
        with ctrl_cols[1]:
            if show_hazard:
                _level_options = ["Major Warning", "Warning", "Advisory"]
                _level_map = {
                    "Major Warning": "MAJOR_WARNING",
                    "Warning": "WARNING",
                    "Advisory": "ADVISORY",
                }
                selected_levels = st.multiselect(
                    "Alert Levels",
                    options=_level_options,
                    default=_level_options,
                    key="tcvmp_alert_levels",
                    label_visibility="collapsed",
                )
                active_levels = [_level_map[l] for l in selected_levels]
            else:
                active_levels = []
        with ctrl_cols[2]:
            active_layers = []
            default_on = {"phc_health_facilities", "phc_education_facilities"}
            fac_items = list(_FAC_ICONS.items())
            fc1, fc2 = st.columns(2)
            for i, (table, (icon, color, label)) in enumerate(fac_items):
                col = fc1 if i % 2 == 0 else fc2
                with col:
                    on = st.checkbox(
                        label, value=(table in default_on),
                        key=f"tcvmp_lyr_{table}",
                    )
                    if on:
                        active_layers.append(table)
        with ctrl_cols[3]:
            show_hotspots = st.checkbox(
                "Flood Hotspots", value=False, key="tcvmp_lyr_hotspots"
            )
            show_roads = st.checkbox(
                "Road Network", value=False, key="tcvmp_lyr_roads"
            )
        with ctrl_cols[4]:
            mc1, mc2 = st.columns(2)
            with mc1:
                use_3d = st.toggle(
                    "3D", value=False, key="tcvmp_3d_mode",
                )
            with mc2:
                base_map_options = ["OpenStreetMap", "Satellite", "Light", "Dark"]
                selected_base_map = st.radio(
                    "Base Map", base_map_options, index=1,
                    key="tcvmp_base_map",
                    horizontal=True,
                    label_visibility="collapsed",
                )

        # Full-viewport map
        fs_map_height = 820
        if show_hazard and active_levels:
            alerts_for_map = {
                d: info for d, info in district_alerts.items()
                if info["alert_level"] in active_levels
            }
        else:
            alerts_for_map = {}
        all_dist_names = list(get_districts_by_region().values())
        flat_dists = [d for dists in all_dist_names for d in dists]

        if tcvmp_ok:
            if use_3d:
                deck = _build_3d_map(
                    alerts_for_map, active_layers, flat_dists,
                    show_hotspots=show_hotspots, show_roads=show_roads,
                    base_map=selected_base_map,
                )
                st.pydeck_chart(
                    deck, height=fs_map_height,
                    key=f"tcvmp_3d_d{day_idx}_{selected_base_map}_fs",
                )
            else:
                fmap = _build_map(
                    alerts_for_map, active_layers, flat_dists,
                    show_hotspots=show_hotspots, show_roads=show_roads,
                )
                st_folium(
                    fmap, height=fs_map_height, use_container_width=True,
                    key=f"tcvmp_map_d{day_idx}_fs",
                )
        else:
            st.info("Map requires TCVMP connection for facility data.")

        # Collapsible analysis panels in fullscreen
        if district_alerts:
            with st.expander("Quick Analysis", expanded=False):
                _render_quick_analysis(district_alerts)
        if tcvmp_ok and district_alerts:
            with st.expander("Detailed Analysis", expanded=False):
                atabs = st.tabs([
                    "Infrastructure Exposure",
                    "Flood Risk Assessment",
                    "Climate Indicators",
                    "Transport & Population",
                ])
                with atabs[0]:
                    _render_infrastructure_tab(district_alerts)
                with atabs[1]:
                    _render_flood_risk_tab(district_alerts)
                with atabs[2]:
                    _render_climate_tab(district_alerts)
                with atabs[3]:
                    _render_transport_tab(district_alerts)

        # Stop here — don't render the normal layout or bottom analysis tabs
        return

    else:
        # -- Normal: sidebar layers | map | quick analysis --
        map_height = 620
        layer_col, map_col, analysis_col = st.columns([1, 3, 1.2])

        # -- Left: Layer controls --
        with layer_col:
            st.markdown("**Layers**")

            st.markdown(
                '<div style="font-size:11px;color:#666;">Hazard</div>',
                unsafe_allow_html=True,
            )
            show_hazard = st.checkbox(
                "Agency Alerts", value=True, key="tcvmp_lyr_hazard"
            )

            # Alert severity filter
            if show_hazard:
                _level_options = ["Major Warning", "Warning", "Advisory"]
                _level_map = {
                    "Major Warning": "MAJOR_WARNING",
                    "Warning": "WARNING",
                    "Advisory": "ADVISORY",
                }
                selected_levels = st.multiselect(
                    "Alert Levels",
                    options=_level_options,
                    default=_level_options,
                    key="tcvmp_alert_levels",
                    label_visibility="collapsed",
                )
                active_levels = [_level_map[l] for l in selected_levels]
            else:
                active_levels = []

            st.markdown(
                '<div style="font-size:11px;color:#666;margin-top:8px;">'
                'Infrastructure</div>',
                unsafe_allow_html=True,
            )
            active_layers = []
            default_on = {"phc_health_facilities", "phc_education_facilities"}
            for table, (icon, color, label) in _FAC_ICONS.items():
                on = st.checkbox(
                    label, value=(table in default_on),
                    key=f"tcvmp_lyr_{table}",
                )
                if on:
                    active_layers.append(table)

            st.markdown(
                '<div style="font-size:11px;color:#666;margin-top:8px;">'
                'Analysis Overlays</div>',
                unsafe_allow_html=True,
            )
            show_hotspots = st.checkbox(
                "Flood Risk Hotspots", value=False, key="tcvmp_lyr_hotspots"
            )
            show_roads = st.checkbox(
                "Road Network", value=False, key="tcvmp_lyr_roads"
            )

            st.markdown(
                '<div style="font-size:11px;color:#666;margin-top:10px;">'
                'Map Mode</div>',
                unsafe_allow_html=True,
            )
            use_3d = st.toggle(
                "3D View", value=False, key="tcvmp_3d_mode",
                help="Switch to 3D view with extruded districts and terrain perspective",
            )
            base_map_options = ["OpenStreetMap", "Satellite", "Light", "Dark"]
            selected_base_map = st.radio(
                "Base Map", base_map_options, index=1,
                key="tcvmp_base_map",
                horizontal=True,
                label_visibility="collapsed",
            )

        # -- Centre: Map --
        with map_col:
            if show_hazard and active_levels:
                alerts_for_map = {
                    d: info for d, info in district_alerts.items()
                    if info["alert_level"] in active_levels
                }
            else:
                alerts_for_map = {}
            all_dist_names = list(get_districts_by_region().values())
            flat_dists = [d for dists in all_dist_names for d in dists]

            if tcvmp_ok:
                if use_3d:
                    deck = _build_3d_map(
                        alerts_for_map, active_layers, flat_dists,
                        show_hotspots=show_hotspots, show_roads=show_roads,
                        base_map=selected_base_map,
                    )
                    st.pydeck_chart(deck, height=map_height, key=f"tcvmp_3d_d{day_idx}_{selected_base_map}")
                    st.caption(
                        "Drag to pan, Ctrl+drag to rotate/tilt, scroll to zoom. "
                        "Height = alert severity. Click features for details."
                    )
                else:
                    fmap = _build_map(
                        alerts_for_map, active_layers, flat_dists,
                        show_hotspots=show_hotspots, show_roads=show_roads,
                    )
                    st_folium(
                        fmap, height=map_height, use_container_width=True,
                        key=f"tcvmp_map_d{day_idx}",
                    )
            else:
                st.info("Map requires TCVMP connection for facility data.")

        # -- Right: Quick analysis --
        with analysis_col:
            if district_alerts:
                _render_quick_analysis(district_alerts)
            else:
                st.caption("Select a day with agency alerts to see analysis.")

    # -- Full-width detailed analysis tabs --
    if tcvmp_ok and district_alerts:
        st.markdown("---")
        st.markdown(
            '<div style="background:#f5f5f5;padding:8px 14px;border-radius:6px;'
            'margin-bottom:8px;">'
            '<b style="font-size:14px;">Detailed Analysis</b>'
            '<span style="font-size:11px;margin-left:10px;color:#666;">'
            'TCVMP data cross-referenced with agency hazard zones</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        analysis_tabs = st.tabs([
            "Infrastructure Exposure",
            "Flood Risk Assessment",
            "Climate Indicators",
            "Transport & Population",
        ])

        with analysis_tabs[0]:
            _render_infrastructure_tab(district_alerts)

        with analysis_tabs[1]:
            _render_flood_risk_tab(district_alerts)

        with analysis_tabs[2]:
            _render_climate_tab(district_alerts)

        with analysis_tabs[3]:
            _render_transport_tab(district_alerts)
