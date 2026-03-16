"""Tanzania map widgets — interactive maps with region/district selection.

Features:
  - Click Map: plotly choropleth, click regions/districts to toggle
  - Draw Polygon: folium map with draw tools, select crossing areas
  - Search List: multiselect-only mode
  - District View: toggle district-level boundaries on/off
  - Blue boundary styling matching water-body theme
  - Water bodies (lakes + rivers) rendered on static maps
  - Region labels with white stroke outline
"""

import io
import json

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import geopandas as gpd
import pandas as pd
import plotly.express as px
import folium
from folium.plugins import Draw
from branca.element import MacroElement
from jinja2 import Template
import streamlit as st
from streamlit_folium import st_folium
from shapely.geometry import shape as shapely_shape, Polygon, box


class _BoundsLock(MacroElement):
    """Inject JS into folium's own map script to hard-lock pan/zoom bounds."""
    _template = Template("""
        {% macro script(this, kwargs) %}
            var _map = {{ this._parent.get_name() }};
            var _sw = L.latLng({{ this.south }}, {{ this.west }});
            var _ne = L.latLng({{ this.north }}, {{ this.east }});
            _map.setMaxBounds(L.latLngBounds(_sw, _ne));
            _map.options.maxBoundsViscosity = 1.0;
            _map.setMinZoom({{ this.min_zoom }});
            _map.setMaxZoom({{ this.max_zoom }});
        {% endmacro %}
    """)

    def __init__(self, bounds, min_zoom=6, max_zoom=10):
        super().__init__()
        self.south = bounds[0][0]
        self.west = bounds[0][1]
        self.north = bounds[1][0]
        self.east = bounds[1][1]
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom


class _DrawStyler(MacroElement):
    """Force fill color on every drawn shape via draw:created event."""
    _template = Template("""
        {% macro script(this, kwargs) %}
            var _map = {{ this._parent.get_name() }};
            _map.on('draw:created', function(e) {
                var layer = e.layer;
                if (layer.setStyle) {
                    layer.setStyle({
                        stroke: true,
                        color: '{{ this.stroke_color }}',
                        weight: {{ this.stroke_weight }},
                        opacity: 1.0,
                        fill: true,
                        fillColor: '{{ this.fill_color }}',
                        fillOpacity: {{ this.fill_opacity }}
                    });
                }
            });
        {% endmacro %}
    """)

    def __init__(self, fill_color, stroke_color="#000000",
                 stroke_weight=2.5, fill_opacity=0.55):
        super().__init__()
        self.fill_color = fill_color
        self.stroke_color = stroke_color
        self.stroke_weight = stroke_weight
        self.fill_opacity = fill_opacity

from .config import (
    load_regions_geodata, load_districts_geodata,
    load_lakes_geodata, load_rivers_geodata,
    DEFAULT_COLORS, MAP_COLORS, REGION_LABEL_ADJUSTMENTS,
)

# Geographic extent
_GEO_XLIM = (28.5, 41.0)
_GEO_YLIM = (-12.0, 0.5)
_TZ_CENTER = [-6.5, 34.5]

# Boundary palette — black
_EDGE = "#000000"             # Region boundaries
_EDGE_LIGHT = "#333333"       # District boundaries
_EDGE_COUNTRY = "#000000"     # Country outline


# ---------------------------------------------------------------------------
# Cached GeoDataFrame loaders
# ---------------------------------------------------------------------------

@st.cache_data
def _get_regions_gdf():
    geojson = load_regions_geodata()
    features = []
    for f in geojson["features"]:
        features.append({
            "display_name": f["properties"]["display_name"],
            "geometry": shapely_shape(f["geometry"]),
        })
    return gpd.GeoDataFrame(features, geometry="geometry")


@st.cache_data
def _get_districts_gdf():
    geojson = load_districts_geodata()
    features = []
    for f in geojson["features"]:
        features.append({
            "display_name": f["properties"]["display_name"],
            "region": f["properties"].get("region", ""),
            "geometry": shapely_shape(f["geometry"]),
        })
    return gpd.GeoDataFrame(features, geometry="geometry")


@st.cache_data
def _get_regions_geojson():
    gdf = _get_regions_gdf()
    return json.loads(gdf.to_json())


@st.cache_data
def _get_districts_geojson():
    gdf = _get_districts_gdf()
    return json.loads(gdf.to_json())


@st.cache_data
def _get_region_names_sorted():
    gdf = _get_regions_gdf()
    return sorted(gdf["display_name"].tolist())


@st.cache_data
def _get_district_names_sorted():
    gdf = _get_districts_gdf()
    return sorted(gdf["display_name"].tolist())


# ---------------------------------------------------------------------------
# Shared rendering helpers (matplotlib static maps)
# ---------------------------------------------------------------------------

def _draw_water_bodies(ax, linewidth_scale: float = 1.0):
    """Draw lakes (blue outline, no fill) and rivers (blue lines)."""
    lakes = load_lakes_geodata()
    rivers = load_rivers_geodata()
    water = MAP_COLORS["water"]
    if lakes is not None and len(lakes) > 0:
        lakes.plot(ax=ax, facecolor="none", edgecolor=water,
                   linewidth=0.8 * linewidth_scale, zorder=2)
    if rivers is not None and len(rivers) > 0:
        rivers.plot(ax=ax, color=water,
                    linewidth=0.5 * linewidth_scale, zorder=2)


def _add_region_labels(ax, gdf, fontsize=4.5, color="#000000",
                       show_adjustments=True):
    """Add region labels with white stroke outline for readability."""
    for _, row in gdf.iterrows():
        name = row["display_name"]
        centroid = row["geometry"].representative_point()
        x, y = centroid.x, centroid.y

        if show_adjustments and name in REGION_LABEL_ADJUSTMENTS:
            dx, dy = REGION_LABEL_ADJUSTMENTS[name]
            x += dx
            y += dy

        ax.text(
            x, y, name, fontsize=fontsize,
            ha="center", va="center", color=color,
            fontfamily="sans-serif", fontweight="normal",
            path_effects=[
                pe.withStroke(linewidth=1.5, foreground="white"),
            ],
        )


# ---------------------------------------------------------------------------
# Interactive plotly region map (click to select/deselect)
# ---------------------------------------------------------------------------

def render_interactive_region_map(
    key_prefix: str,
    sel_key: str,
    color: str = "#FFFF00",
    height: int = 500,
):
    """Interactive region map — click regions to toggle selection."""
    if sel_key not in st.session_state:
        st.session_state[sel_key] = []

    selected = set(st.session_state[sel_key])
    geojson = _get_regions_geojson()
    names = _get_region_names_sorted()

    df = pd.DataFrame({
        "region": names,
        "value": [1 if n in selected else 0 for n in names],
    })

    fig = px.choropleth(
        df,
        geojson=geojson,
        locations="region",
        featureidkey="properties.display_name",
        color="value",
        color_continuous_scale=[[0, "#FFFFFF"], [1, color]],
        range_color=[0, 1],
        hover_name="region",
        hover_data={"value": False, "region": False},
    )
    fig.update_geos(
        fitbounds="locations",
        visible=False,
    )
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_showscale=False,
        paper_bgcolor="white",
        geo_bgcolor="white",
        dragmode=False,
    )
    fig.update_traces(
        marker_line_color=_EDGE,
        marker_line_width=0.8,
    )

    event = st.plotly_chart(
        fig,
        on_select="rerun",
        selection_mode=["points", "box", "lasso"],
        key=f"{key_prefix}_chart",
        use_container_width=True,
    )

    # Handle click — toggle the clicked region(s).
    last_event_key = f"{key_prefix}_last_event"
    if event and event.selection and event.selection.points:
        clicked = set()
        for p in event.selection.points:
            loc = p.get("location") or p.get("hovertext") or p.get("customdata")
            if isinstance(loc, (list, tuple)):
                loc = loc[0] if loc else None
            if loc and loc in names:
                clicked.add(loc)
        clicked_frozen = frozenset(clicked)
        if clicked and clicked_frozen != st.session_state.get(last_event_key):
            st.session_state[last_event_key] = clicked_frozen
            new_selected = selected.symmetric_difference(clicked)
            st.session_state[sel_key] = sorted(new_selected)
            st.rerun()
    else:
        st.session_state.pop(last_event_key, None)


def render_interactive_district_map(
    key_prefix: str,
    sel_key: str,
    color: str = "#FFFF00",
    height: int = 550,
):
    """Interactive district map — click districts to toggle selection."""
    if sel_key not in st.session_state:
        st.session_state[sel_key] = []

    selected = set(st.session_state[sel_key])
    geojson = _get_districts_geojson()
    names = _get_district_names_sorted()

    df = pd.DataFrame({
        "district": names,
        "value": [1 if n in selected else 0 for n in names],
    })

    fig = px.choropleth(
        df,
        geojson=geojson,
        locations="district",
        featureidkey="properties.display_name",
        color="value",
        color_continuous_scale=[[0, "#F5F5F5"], [1, color]],
        range_color=[0, 1],
        hover_name="district",
        hover_data={"value": False, "district": False},
    )
    fig.update_geos(
        fitbounds="locations",
        visible=False,
    )
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_showscale=False,
        paper_bgcolor="white",
        geo_bgcolor="white",
        dragmode=False,
    )
    fig.update_traces(
        marker_line_color=_EDGE,
        marker_line_width=0.6,
    )

    # Add region boundaries as thicker overlay
    region_gdf = _get_regions_gdf()
    for _, row in region_gdf.iterrows():
        geom = row["geometry"]
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            lons, lats = zip(*poly.exterior.coords)
            fig.add_scattergeo(
                lon=lons, lat=lats,
                mode="lines",
                line=dict(color=_EDGE_COUNTRY, width=1.8),
                showlegend=False,
                hoverinfo="skip",
            )

    event = st.plotly_chart(
        fig,
        on_select="rerun",
        selection_mode=["points", "box", "lasso"],
        key=f"{key_prefix}_dchart",
        use_container_width=True,
    )

    # Handle click — toggle the clicked district(s).
    last_event_key = f"{key_prefix}_last_devent"
    if event and event.selection and event.selection.points:
        clicked = set()
        for p in event.selection.points:
            loc = p.get("location") or p.get("hovertext") or p.get("customdata")
            if isinstance(loc, (list, tuple)):
                loc = loc[0] if loc else None
            if loc and loc in names:
                clicked.add(loc)
        clicked_frozen = frozenset(clicked)
        if clicked and clicked_frozen != st.session_state.get(last_event_key):
            st.session_state[last_event_key] = clicked_frozen
            new_selected = selected.symmetric_difference(clicked)
            st.session_state[sel_key] = sorted(new_selected)
            st.rerun()
    else:
        st.session_state.pop(last_event_key, None)


# ---------------------------------------------------------------------------
# Static matplotlib maps — pipeline-quality rendering
# ---------------------------------------------------------------------------

@st.cache_data
def _render_region_image(
    selected_json: str,
    fill_color: str,
    show_districts: bool = False,
    width: int = 900,
    height: int = 750,
) -> bytes:
    """Render a region map as PNG bytes with blue boundaries."""
    selected = set(eval(selected_json))
    gdf = _get_regions_gdf()

    dpi = 150
    fig, ax = plt.subplots(1, 1, figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    if show_districts:
        dist_gdf = _get_districts_gdf()
        dist_colors = []
        for _, drow in dist_gdf.iterrows():
            if drow["region"] in selected:
                dist_colors.append(fill_color)
            else:
                dist_colors.append(MAP_COLORS["no_data"])
        dist_copy = dist_gdf.copy()
        dist_copy["_color"] = dist_colors
        dist_copy.plot(
            ax=ax, color=dist_copy["_color"],
            edgecolor=_EDGE_LIGHT, linewidth=0.2, zorder=1,
        )
        gdf.boundary.plot(ax=ax, color=_EDGE, linewidth=0.8, zorder=3)
    else:
        colors = []
        for _, row in gdf.iterrows():
            if row["display_name"] in selected:
                colors.append(fill_color)
            else:
                colors.append(MAP_COLORS["no_data"])
        gdf_copy = gdf.copy()
        gdf_copy["_color"] = colors
        gdf_copy.plot(
            ax=ax, color=gdf_copy["_color"],
            edgecolor=_EDGE, linewidth=0.6,
        )

    lw_scale = 1.2 if width >= 800 else 0.8
    _draw_water_bodies(ax, linewidth_scale=lw_scale)

    label_size = 4.5 if width >= 800 else 3.5
    _add_region_labels(ax, gdf, fontsize=label_size, color="#000000")

    ax.set_xlim(*_GEO_XLIM)
    ax.set_ylim(*_GEO_YLIM)
    ax.set_aspect("equal")
    ax.set_axis_off()

    if selected:
        patches = [
            mpatches.Patch(color=fill_color, label=f"Selected ({len(selected)})"),
            mpatches.Patch(facecolor=MAP_COLORS["no_data"], edgecolor=_EDGE,
                           linewidth=0.5, label="No warning"),
        ]
        ax.legend(handles=patches, loc="lower left", fontsize=7, framealpha=0.9)

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=0.02, facecolor="white", edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


@st.cache_data
def _render_district_image(
    district_colors_json: str,
    width: int = 900,
    height: int = 750,
) -> bytes:
    """Render a district map as PNG bytes (DMD multi-tier view)."""
    district_colors = eval(district_colors_json)
    gdf = _get_districts_gdf()
    region_gdf = _get_regions_gdf()

    dpi = 150
    fig, ax = plt.subplots(1, 1, figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    colors = []
    for _, row in gdf.iterrows():
        name = row["display_name"]
        colors.append(district_colors.get(name, MAP_COLORS["no_data"]))

    gdf_copy = gdf.copy()
    gdf_copy["_color"] = colors

    gdf_copy.plot(
        ax=ax, color=gdf_copy["_color"],
        edgecolor=_EDGE_LIGHT, linewidth=0.15,
    )

    region_gdf.boundary.plot(ax=ax, color=_EDGE, linewidth=0.6)
    _draw_water_bodies(ax, linewidth_scale=0.8)
    _add_region_labels(ax, region_gdf, fontsize=3.5, color="#000000")

    ax.set_xlim(*_GEO_XLIM)
    ax.set_ylim(*_GEO_YLIM)
    ax.set_aspect("equal")
    ax.set_axis_off()

    legend_items = []
    tier_labels = {
        "#FF0000": "Major Warning",
        "#FFA500": "Warning",
        "#FFFF00": "Advisory",
    }
    for hex_color, label in tier_labels.items():
        if hex_color in district_colors.values():
            legend_items.append(mpatches.Patch(color=hex_color, label=label))
    if legend_items:
        ax.legend(handles=legend_items, loc="lower left", fontsize=7,
                  framealpha=0.9)

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=0.02, facecolor="white", edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


def render_region_map(
    selected_regions: set[str],
    color: str = None,
    show_districts: bool = False,
    height: int = 420,
):
    """Render region map as a smooth static image."""
    fill_color = color or DEFAULT_COLORS["advisory"]
    sel_json = repr(sorted(selected_regions))
    img_bytes = _render_region_image(sel_json, fill_color,
                                     show_districts=show_districts)
    st.image(img_bytes, width="stretch")


def render_district_map(
    selected_districts: dict[str, str],
    height: int = 420,
):
    """Render district map as a smooth static image."""
    dc_json = repr(dict(sorted(selected_districts.items())))
    img_bytes = _render_district_image(dc_json)
    st.image(img_bytes, width="stretch")


# ---------------------------------------------------------------------------
# Folium draw map — draw polygons/rectangles to select areas
# ---------------------------------------------------------------------------

def _geojson_to_shapely(geojson_feature: dict):
    """Convert a GeoJSON feature (or bare geometry) to a shapely shape.

    Handles circles specially: Leaflet Draw exports them as Point geometry
    with a ``radius`` property (meters).  We buffer the point to produce a
    proper polygon so intersection checks work.
    """
    if not isinstance(geojson_feature, dict):
        return None

    # Accept either a full Feature or a bare geometry dict
    if geojson_feature.get("type") == "Feature":
        geom = geojson_feature.get("geometry")
        props = geojson_feature.get("properties", {})
    else:
        geom = geojson_feature
        props = {}

    if not geom:
        return None

    try:
        geo = shapely_shape(geom)
        if not geo.is_valid:
            geo = geo.buffer(0)  # attempt fix
            if not geo.is_valid:
                return None

        # Circle: Point + radius → buffer to polygon
        if geom.get("type") == "Point" and props.get("radius"):
            radius_m = float(props["radius"])
            # 1° latitude ≈ 111 320 m; approximate for Tanzania latitudes
            radius_deg = radius_m / 111_320
            geo = geo.buffer(radius_deg, resolution=32)

        # Skip zero-area geometries (bare points without radius, etc.)
        if geo.is_empty or (hasattr(geo, "area") and geo.area == 0):
            return None

        return geo
    except Exception:
        return None


def _find_intersecting(drawn_shapes: list, level: str) -> set[str]:
    """Find regions or districts that intersect with drawn shapes."""
    if level == "districts":
        gdf = _get_districts_gdf()
    else:
        gdf = _get_regions_gdf()

    found = set()
    for geo_shape in drawn_shapes:
        for _, row in gdf.iterrows():
            if row["geometry"].intersects(geo_shape):
                found.add(row["display_name"])
    return found


@st.cache_data
def _get_lakes_geojson():
    lakes = load_lakes_geodata()
    if lakes is not None and len(lakes) > 0:
        return json.loads(lakes.to_json())
    return None


@st.cache_data
def _get_rivers_geojson():
    rivers = load_rivers_geodata()
    if rivers is not None and len(rivers) > 0:
        return json.loads(rivers.to_json())
    return None


@st.cache_data
def _get_tz_mask_geojson() -> dict:
    """Build a GeoJSON polygon covering everything EXCEPT Tanzania — white mask."""
    gdf = _get_regions_gdf()
    country = gdf.dissolve().geometry.iloc[0]
    # World bounding box minus Tanzania
    world = box(-180, -90, 180, 90)
    mask = world.difference(country)
    return json.loads(gpd.GeoSeries([mask]).to_json())


# Tanzania bounds for map locking: [[south, west], [north, east]]
_TZ_BOUNDS = [[-12.5, 28.0], [1.0, 41.5]]


def _render_folium_draw_map(
    key_prefix: str,
    sel_key: str,
    color: str,
    level: str,
    show_districts: bool,
    height: int = 500,
):
    """Folium map with drawing tools for spatial selection.

    Simple approach: render map with Draw plugin, read all_drawings +
    last_active_drawing from st_folium, find intersecting areas, show
    Apply button.
    """
    if sel_key not in st.session_state:
        st.session_state[sel_key] = []

    selected = set(st.session_state[sel_key])
    _WATER_BLUE = MAP_COLORS["water"]

    # Create folium map locked to Tanzania
    m = folium.Map(
        location=_TZ_CENTER,
        zoom_start=6,
        min_zoom=6,
        max_zoom=9,
        tiles=None,
        control_scale=True,
        zoom_control=True,
        scrollWheelZoom=True,
    )
    m.fit_bounds(_TZ_BOUNDS)
    m.options["maxBounds"] = _TZ_BOUNDS
    m.options["maxBoundsViscosity"] = 1.0
    _BoundsLock(_TZ_BOUNDS, min_zoom=6, max_zoom=9).add_to(m)

    # Minimal tile layer
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        attr="CartoDB",
        name="Background",
        control=False,
    ).add_to(m)

    # White mask outside Tanzania
    mask_gj = _get_tz_mask_geojson()
    folium.GeoJson(
        mask_gj,
        style_function=lambda _: {
            "fillColor": "#FFFFFF",
            "color": "#FFFFFF",
            "weight": 0,
            "fillOpacity": 1.0,
        },
    ).add_to(m)

    # Region boundaries
    region_geojson = _get_regions_geojson()
    folium.GeoJson(
        region_geojson,
        name="Regions",
        style_function=lambda f: {
            "fillColor": "#FFFFFF",
            "color": "#000000",
            "weight": 1.0,
            "fillOpacity": 0.05,
        },
        tooltip=folium.GeoJsonTooltip(fields=["display_name"], aliases=["Region:"]),
    ).add_to(m)

    # District boundaries if needed
    if show_districts or level == "districts":
        district_geojson = _get_districts_geojson()
        if level == "districts":
            folium.GeoJson(
                district_geojson,
                name="Districts",
                style_function=lambda f: {
                    "fillColor": "#FFFFFF",
                    "color": "#333333",
                    "weight": 0.4,
                    "fillOpacity": 0.02,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["display_name"], aliases=["District:"]
                ),
            ).add_to(m)
            folium.GeoJson(
                region_geojson,
                style_function=lambda _: {
                    "fillColor": "transparent",
                    "color": "#000000",
                    "weight": 1.0,
                    "fillOpacity": 0,
                },
            ).add_to(m)
        else:
            folium.GeoJson(
                district_geojson,
                name="Districts",
                style_function=lambda _: {
                    "fillColor": "transparent",
                    "color": "#555555",
                    "weight": 0.3,
                    "fillOpacity": 0,
                },
            ).add_to(m)

    # Water bodies
    lakes_gj = _get_lakes_geojson()
    if lakes_gj:
        folium.GeoJson(
            lakes_gj,
            name="Lakes",
            style_function=lambda _: {
                "fillColor": "transparent",
                "color": _WATER_BLUE,
                "weight": 1.2,
                "fillOpacity": 0,
            },
        ).add_to(m)

    rivers_gj = _get_rivers_geojson()
    if rivers_gj:
        folium.GeoJson(
            rivers_gj,
            name="Rivers",
            style_function=lambda _: {
                "color": _WATER_BLUE,
                "weight": 1.0,
                "fillOpacity": 0,
            },
        ).add_to(m)

    # Draw controls
    shape_opts = {
        "stroke": True,
        "color": "#000000",
        "weight": 2.5,
        "opacity": 1.0,
        "fill": True,
        "fillColor": color,
        "fillOpacity": 0.55,
    }
    Draw(
        draw_options={
            "polyline": False,
            "polygon": {"allowIntersection": False, "shapeOptions": shape_opts},
            "rectangle": {"shapeOptions": shape_opts},
            "circle": {"shapeOptions": shape_opts},
            "circlemarker": False,
            "marker": False,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(m)

    # Session key for persisting drawings across reruns
    drawings_store = f"{key_prefix}_draw_store"

    def _on_draw_change():
        """Callback: capture drawing data into session before rerun clears it."""
        folium_key = f"{key_prefix}_folium"
        data = st.session_state.get(folium_key)
        if data and isinstance(data, dict):
            raw = data.get("all_drawings")
            if raw and isinstance(raw, list) and len(raw) > 0:
                st.session_state[drawings_store] = raw
            last = data.get("last_active_drawing")
            if last and isinstance(last, dict) and not raw:
                st.session_state[drawings_store] = [last]

    # Render map with on_change callback
    result = st_folium(
        m,
        height=height,
        key=f"{key_prefix}_folium",
        returned_objects=["all_drawings", "last_active_drawing"],
        use_container_width=True,
        on_change=_on_draw_change,
    )

    # --- Process drawings from callback store OR current result ---
    drawn_shapes = []

    # First try current result
    raw_drawings = None
    if result:
        raw_drawings = result.get("all_drawings")
        if not raw_drawings:
            last = result.get("last_active_drawing")
            if last and isinstance(last, dict):
                raw_drawings = [last]

    # Fall back to stored drawings from callback
    if not raw_drawings:
        raw_drawings = st.session_state.get(drawings_store)

    if raw_drawings:
        # Also update store
        st.session_state[drawings_store] = raw_drawings
        for drawing in raw_drawings:
            if not isinstance(drawing, dict):
                continue
            geo = _geojson_to_shapely(drawing)
            if geo:
                drawn_shapes.append(geo)

    found = set()
    if drawn_shapes:
        found = _find_intersecting(drawn_shapes, level)

    # Show results + Apply / Clear buttons
    unit = "districts" if level == "districts" else "regions"

    if found:
        new_found = found - selected
        already = found & selected
        st.info(
            f"Drawn shapes cover **{len(found)} {unit}**: "
            f"{', '.join(sorted(found))}"
        )
        btn_cols = st.columns([3, 1])
        with btn_cols[0]:
            if new_found:
                if st.button(
                    f"Apply — add {len(new_found)} {unit} to selection",
                    key=f"{key_prefix}_apply",
                    type="primary",
                    use_container_width=True,
                ):
                    combined = selected | found
                    st.session_state[sel_key] = sorted(combined)
                    st.session_state.pop(drawings_store, None)
                    st.rerun()
            elif already:
                st.caption(f"All {len(already)} {unit} already selected.")
        with btn_cols[1]:
            if st.button("Clear", key=f"{key_prefix}_clear_draw",
                         use_container_width=True):
                st.session_state.pop(drawings_store, None)
                st.rerun()
    elif drawn_shapes:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.caption("Drawn shapes don't cover any " + unit + ".")
        with c2:
            if st.button("Clear", key=f"{key_prefix}_clear_draw2",
                         use_container_width=True):
                st.session_state.pop(drawings_store, None)
                st.rerun()


def render_drawable_region_map(
    key_prefix: str,
    sel_key: str,
    color: str = "#FFFF00",
    show_districts: bool = False,
):
    """Draw map for region selection."""
    _render_folium_draw_map(
        key_prefix, sel_key, color,
        level="regions", show_districts=show_districts,
    )


# ---------------------------------------------------------------------------
# Unified map selector — combines Click, Draw, Regions/Districts
# ---------------------------------------------------------------------------

def render_map_selector(
    key_prefix: str,
    sel_key: str,
    color: str = "#FFFF00",
    all_regions: list[str] = None,
    allow_districts: bool = True,
):
    """Smart unified map widget with mode tabs, region/district level toggle.

    Provides:
      - Click Map: click regions/districts to toggle selection (plotly)
      - Draw Polygon: folium map with draw tools to select crossing areas
      - Search List: multiselect-only mode
      - Level toggle: Regions vs Districts

    Returns dict: {"regions": [...], "districts": [...]}
    """
    if sel_key not in st.session_state:
        st.session_state[sel_key] = []

    dist_key = f"{key_prefix}_districts"
    if dist_key not in st.session_state:
        st.session_state[dist_key] = []

    if all_regions is None:
        all_regions = _get_region_names_sorted()
    all_districts = _get_district_names_sorted()

    # --- Controls row ---
    ctrl_cols = st.columns([3, 1.5, 1.5, 1])
    with ctrl_cols[0]:
        sel_mode = st.radio(
            "Selection mode", ["Click Map", "Draw Polygon", "Search List"],
            horizontal=True, key=f"{key_prefix}_mode",
        )
    with ctrl_cols[1]:
        geo_level = "regions"
        if allow_districts:
            geo_level = st.radio(
                "Level", ["Regions", "Districts"],
                horizontal=True, key=f"{key_prefix}_geo_level",
            ).lower()
    with ctrl_cols[2]:
        show_dist = st.toggle(
            "Show districts", value=False,
            key=f"{key_prefix}_show_dist",
            help="Overlay district boundaries for finer geographic detail",
            disabled=(geo_level == "districts"),
        )
    with ctrl_cols[3]:
        active_key = dist_key if geo_level == "districts" else sel_key
        count = len(st.session_state[active_key])
        unit = "district" if geo_level == "districts" else "region"
        if count:
            st.markdown(
                f'<div style="padding:4px 8px;background:#e3f2fd;'
                f'border-radius:6px;text-align:center;margin-top:4px;'
                f'font-size:13px;">'
                f'<strong>{count}</strong> {unit}(s)</div>',
                unsafe_allow_html=True,
            )

    effective_show_dist = show_dist or (geo_level == "districts")

    # --- Map rendering ---
    if sel_mode == "Click Map":
        if geo_level == "districts":
            render_interactive_district_map(
                key_prefix=f"{key_prefix}_dclk",
                sel_key=dist_key,
                color=color,
            )
        else:
            render_interactive_region_map(
                key_prefix=f"{key_prefix}_clk",
                sel_key=sel_key,
                color=color,
            )
            if effective_show_dist:
                selected_set = set(st.session_state[sel_key])
                if selected_set:
                    st.caption("District overlay preview:")
                    render_region_map(selected_set, color=color,
                                     show_districts=True, height=300)

    elif sel_mode == "Draw Polygon":
        draw_level = geo_level
        draw_key = dist_key if draw_level == "districts" else sel_key
        st.caption(
            f"Draw shapes on the map — all {draw_level} the shape crosses "
            f"will be selected (e.g. around water bodies, across borders)"
        )
        _render_folium_draw_map(
            key_prefix=f"{key_prefix}_drw",
            sel_key=draw_key,
            color=color,
            level=draw_level,
            show_districts=effective_show_dist,
        )

    # --- Multiselect always visible ---
    if geo_level == "districts":
        label = ("Selected districts" if sel_mode != "Search List"
                 else "Search and select districts")
        st.multiselect(label, all_districts, key=dist_key)
    else:
        label = ("Selected regions" if sel_mode != "Search List"
                 else "Search and select regions")
        st.multiselect(label, all_regions, key=sel_key)

    # Collect drawn shapes from session state (if any were drawn)
    drawings_key = f"{key_prefix}_drw_saved_drawings"
    drawn_features = list(st.session_state.get(drawings_key, []))

    return {
        "regions": list(st.session_state[sel_key]),
        "districts": list(st.session_state[dist_key]),
        "drawn_shapes": drawn_features,
    }


# ---------------------------------------------------------------------------
# DMD District Tier Map Selector — click/draw to assign districts to tiers
# ---------------------------------------------------------------------------

_TIER_DEFS = [
    ("advisory", "Advisory", "#FFFF00", "#000"),
    ("warning", "Warning", "#FFA500", "#FFF"),
    ("major_warning", "Major Warning", "#FF0000", "#FFF"),
]

_TIER_LABEL_MAP = {label: key for key, label, _, _ in _TIER_DEFS}


def render_district_tier_map_selector(
    key_prefix: str,
    tier_keys: dict[str, str],
    tier_colors: dict[str, str],
    height: int = 550,
):
    """Interactive district map with Click / Draw / Search for DMD tier selection.

    Same selection modes as TMA (click map, draw polygon, search list)
    but targeting the three-tier district system.

    Args:
        key_prefix: Unique key prefix (e.g. "dmd_d0_tmap")
        tier_keys: tier name → session state key, e.g.
                   {"major_warning": "dmd_d0_tier_major_warning", ...}
        tier_colors: tier name → hex color, e.g.
                     {"major_warning": "#FF0000", ...}
        height: Map height in pixels
    """
    # Ensure all tier keys exist
    for sk in tier_keys.values():
        if sk not in st.session_state:
            st.session_state[sk] = []

    # --- Controls ---
    ctrl_cols = st.columns([3, 2.5, 1])

    with ctrl_cols[0]:
        sel_mode = st.radio(
            "Selection mode",
            ["Click Map", "Draw Polygon", "Search List"],
            horizontal=True,
            key=f"{key_prefix}_mode",
        )

    with ctrl_cols[1]:
        tier_labels = [label for _, label, _, _ in _TIER_DEFS]
        active_label = st.radio(
            "Active tier",
            tier_labels,
            horizontal=True,
            key=f"{key_prefix}_active_tier",
            index=0,
        )
        active_tier = _TIER_LABEL_MAP[active_label]

    with ctrl_cols[2]:
        active_count = len(st.session_state.get(tier_keys[active_tier], []))
        _, _, bg, tc = next(d for d in _TIER_DEFS if d[0] == active_tier)
        bg = tier_colors.get(active_tier, bg)
        st.markdown(
            f'<div style="padding:6px 8px;background:{bg};color:{tc};'
            f'border-radius:6px;text-align:center;margin-top:6px;'
            f'font-size:13px;font-weight:bold;">'
            f'{active_count} districts</div>',
            unsafe_allow_html=True,
        )

    active_sk = tier_keys[active_tier]
    active_color = tier_colors.get(active_tier, "#FFFF00")

    # --- Map ---
    if sel_mode == "Click Map":
        _render_tier_click_map(
            key_prefix=f"{key_prefix}_clk",
            tier_keys=tier_keys,
            tier_colors=tier_colors,
            active_tier=active_tier,
            height=height,
        )
    elif sel_mode == "Draw Polygon":
        st.caption(
            f"Draw shapes on the map — all districts the shape crosses "
            f"will be added to **{active_label}**"
        )
        _render_folium_draw_map(
            key_prefix=f"{key_prefix}_drw",
            sel_key=active_sk,
            color=active_color,
            level="districts",
            show_districts=True,
            height=height,
        )

    # --- Tier summary bar ---
    cols = st.columns(3)
    for i, (tier_key, tier_label, default_bg, default_tc) in enumerate(_TIER_DEFS):
        with cols[i]:
            n = len(st.session_state.get(tier_keys[tier_key], []))
            bg = tier_colors.get(tier_key, default_bg)
            tc = default_tc
            st.markdown(
                f'<div style="background:{bg};color:{tc};padding:6px 10px;'
                f'border-radius:4px;text-align:center;font-size:12px;">'
                f'<b>{tier_label}</b>: {n} districts</div>',
                unsafe_allow_html=True,
            )


def _render_tier_click_map(
    key_prefix: str,
    tier_keys: dict[str, str],
    tier_colors: dict[str, str],
    active_tier: str,
    height: int = 550,
):
    """Plotly choropleth: districts colored by tier, click to assign/remove."""
    names = _get_district_names_sorted()
    geojson = _get_districts_geojson()

    # Build district → tier lookup
    district_tier = {}
    for tier_name, sk in tier_keys.items():
        for d in st.session_state.get(sk, []):
            district_tier[d] = tier_name

    # Numeric encoding: 0=unselected, 1=advisory, 2=warning, 3=major
    tier_val = {"advisory": 1, "warning": 2, "major_warning": 3}
    values = [tier_val.get(district_tier.get(n), 0) for n in names]

    # Discrete color scale (evenly spaced across 0→3)
    c_none = "#F0F0F0"
    c_adv = tier_colors.get("advisory", "#FFFF00")
    c_warn = tier_colors.get("warning", "#FFA500")
    c_major = tier_colors.get("major_warning", "#FF0000")
    colorscale = [
        [0.00, c_none], [0.16, c_none],
        [0.17, c_adv],  [0.49, c_adv],
        [0.50, c_warn], [0.82, c_warn],
        [0.83, c_major], [1.00, c_major],
    ]

    tier_display = {
        "advisory": "Advisory", "warning": "Warning",
        "major_warning": "Major Warning",
    }
    hover = [tier_display.get(district_tier.get(n), "—") for n in names]

    df = pd.DataFrame({
        "district": names, "value": values, "tier": hover,
    })

    fig = px.choropleth(
        df,
        geojson=geojson,
        locations="district",
        featureidkey="properties.display_name",
        color="value",
        color_continuous_scale=colorscale,
        range_color=[0, 3],
        hover_name="district",
        hover_data={"value": False, "district": False, "tier": True},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_showscale=False,
        paper_bgcolor="white",
        geo_bgcolor="white",
        dragmode=False,
    )
    fig.update_traces(marker_line_color=_EDGE, marker_line_width=0.5)

    # Region boundaries overlay
    region_gdf = _get_regions_gdf()
    for _, row in region_gdf.iterrows():
        geom = row["geometry"]
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            lons, lats = zip(*poly.exterior.coords)
            fig.add_scattergeo(
                lon=lons, lat=lats,
                mode="lines",
                line=dict(color=_EDGE_COUNTRY, width=1.5),
                showlegend=False,
                hoverinfo="skip",
            )

    event = st.plotly_chart(
        fig,
        on_select="rerun",
        selection_mode=["points", "box", "lasso"],
        key=f"{key_prefix}_chart",
        use_container_width=True,
    )

    # Handle click — assign to / remove from active tier
    last_key = f"{key_prefix}_last_ev"
    if event and event.selection and event.selection.points:
        clicked = set()
        for p in event.selection.points:
            loc = p.get("location") or p.get("hovertext") or p.get("customdata")
            if isinstance(loc, (list, tuple)):
                loc = loc[0] if loc else None
            if loc and loc in names:
                clicked.add(loc)
        frozen = frozenset(clicked)
        if clicked and frozen != st.session_state.get(last_key):
            st.session_state[last_key] = frozen

            active_sk = tier_keys[active_tier]
            active_set = set(st.session_state.get(active_sk, []))

            for d in clicked:
                cur = district_tier.get(d)
                if cur == active_tier:
                    # Toggle off
                    active_set.discard(d)
                else:
                    # Remove from other tier if assigned
                    if cur and cur in tier_keys:
                        other_sk = tier_keys[cur]
                        other = set(st.session_state.get(other_sk, []))
                        other.discard(d)
                        st.session_state[other_sk] = sorted(other)
                    # Add to active tier
                    active_set.add(d)

            st.session_state[active_sk] = sorted(active_set)
            st.rerun()
    else:
        st.session_state.pop(last_key, None)
