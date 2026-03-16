"""Map generator for Tanzania early warning bulletins.

Generates Tanzania maps with colored district/region polygons matching
the exact visual style of the original bulletins:
- Region name labels at polygon centroids
- Thick country border outline
- Warning triangle icons on affected areas
- Blue water bodies (Lake Victoria, Indian Ocean coastline)
"""

from pathlib import Path
from typing import Optional

import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.colors import to_rgba
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from shapely.geometry import box, shape as shapely_shape, Point
from matplotlib.patches import Circle as MplCircle, Polygon as MplPolygon

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
GEODATA_DIR = ASSETS_DIR / "geodata"

# Color palette matching the original bulletins
COLORS = {
    "advisory": "#FFFF00",       # Yellow (ADVISORY/ANGALIZO)
    "warning": "#FFA500",        # Orange (WARNING/TAHADHARI)
    "major_warning": "#FF0000",  # Red (MAJOR WARNING/TAHADHARI KUBWA)
    "no_data": "#FFFFFF",        # White (no warning — matches reference)
    "boundary": "#999999",       # District boundary lines
    "region_boundary": "#444444",  # Region boundary lines (thicker)
    "country_border": "#222222", # Country outline
    "water": "#B0D4F1",         # Water bodies (light blue)
    "background": "#FFFFFF",     # Background
}

# Region label positions (manual adjustments for better placement)
REGION_LABEL_ADJUSTMENTS = {
    "Dar es Salaam": (0.3, -0.15),
    "Kaskazini Unguja": (0.5, 0.1),
    "Kusini Unguja": (0.5, -0.1),
    "Kaskazini Pemba": (0.5, 0.1),
    "Kusini Pemba": (0.5, -0.1),
    "Mjini Magharibi": (0.6, 0.0),
}

# Short display names for map labels
REGION_SHORT_NAMES = {
    "Dar es Salaam": "Dar-es-salaam",
    "Kaskazini Unguja": "Kaskazini Unguja",
    "Kusini Unguja": "Kusini Unguja",
    "Kaskazini Pemba": "Kaskazini Pemba",
    "Kusini Pemba": "Kusini Pemba",
    "Mjini Magharibi": "Mjini Magharibi",
}

# Tanzania bounding box (lon_min, lat_min, lon_max, lat_max)
_TZ_BOUNDS = (28, -12, 41, 1)

# Singleton data cache
_regions_gdf = None
_districts_gdf = None
_country_boundary = None
_lakes_gdf = None
_rivers_gdf = None


def _load_regions() -> gpd.GeoDataFrame:
    """Load Tanzania region boundaries."""
    global _regions_gdf
    if _regions_gdf is None:
        path = GEODATA_DIR / "gadm41_TZA_1.json.zip"
        _regions_gdf = gpd.read_file(f"zip://{path}")
    return _regions_gdf


def _load_districts() -> gpd.GeoDataFrame:
    """Load Tanzania district boundaries."""
    global _districts_gdf
    if _districts_gdf is None:
        path = GEODATA_DIR / "gadm41_TZA_2.json.zip"
        _districts_gdf = gpd.read_file(f"zip://{path}")
    return _districts_gdf


def _get_country_boundary():
    """Get the dissolved country boundary for the thick outline."""
    global _country_boundary
    if _country_boundary is None:
        regions = _load_regions()
        _country_boundary = regions.dissolve()
    return _country_boundary


def _load_lakes() -> gpd.GeoDataFrame:
    """Load Natural Earth lakes clipped to Tanzania's country boundary."""
    global _lakes_gdf
    if _lakes_gdf is None:
        path = GEODATA_DIR / "ne_10m_lakes.zip"
        if path.exists():
            gdf = gpd.read_file(f"zip://{path}")
            # Bounding-box pre-filter then clip to exact country shape
            nearby = gdf.cx[
                _TZ_BOUNDS[0]:_TZ_BOUNDS[2],
                _TZ_BOUNDS[1]:_TZ_BOUNDS[3],
            ]
            country = _get_country_boundary()
            _lakes_gdf = gpd.clip(nearby, country)
        else:
            _lakes_gdf = gpd.GeoDataFrame()
    return _lakes_gdf


def _load_rivers() -> gpd.GeoDataFrame:
    """Load Natural Earth rivers clipped to Tanzania's country boundary."""
    global _rivers_gdf
    if _rivers_gdf is None:
        path = GEODATA_DIR / "ne_10m_rivers.zip"
        if path.exists():
            gdf = gpd.read_file(f"zip://{path}")
            nearby = gdf.cx[
                _TZ_BOUNDS[0]:_TZ_BOUNDS[2],
                _TZ_BOUNDS[1]:_TZ_BOUNDS[3],
            ]
            country = _get_country_boundary()
            _rivers_gdf = gpd.clip(nearby, country)
        else:
            _rivers_gdf = gpd.GeoDataFrame()
    return _rivers_gdf


def _draw_water_bodies(ax, linewidth_scale: float = 1.0):
    """Draw lakes and rivers (clipped to Tanzania boundary) on the map."""
    lakes = _load_lakes()
    rivers = _load_rivers()
    water_color = COLORS["water"]
    if len(lakes) > 0:
        lakes.plot(ax=ax, color=water_color, edgecolor=water_color,
                   linewidth=0.3 * linewidth_scale, zorder=2)
    if len(rivers) > 0:
        rivers.plot(ax=ax, color=water_color,
                    linewidth=0.5 * linewidth_scale, zorder=2)


def _normalize_name(name: str) -> str:
    """Normalize a region/district name for matching."""
    return name.lower().replace(" ", "").replace("-", "").replace("'", "")


def _build_name_mapping(gdf: gpd.GeoDataFrame, name_col: str) -> dict:
    """Build a normalized-name to index mapping."""
    mapping = {}
    for idx, row in gdf.iterrows():
        normalized = _normalize_name(row[name_col])
        mapping[normalized] = idx
        # Also add VARNAME variants if available
        if 'VARNAME_2' in gdf.columns and row.get('VARNAME_2'):
            for variant in str(row['VARNAME_2']).split('|'):
                mapping[_normalize_name(variant)] = idx
    return mapping


def _add_region_labels(ax, regions_gdf, fontsize=4, color='#333333'):
    """Add region name labels at polygon centroids."""
    for idx, row in regions_gdf.iterrows():
        name = row['NAME_1']
        display_name = REGION_SHORT_NAMES.get(name, name)

        # Get centroid
        centroid = row.geometry.representative_point()
        x, y = centroid.x, centroid.y

        # Apply manual adjustments
        if name in REGION_LABEL_ADJUSTMENTS:
            dx, dy = REGION_LABEL_ADJUSTMENTS[name]
            x += dx
            y += dy

        # Add text with white outline for readability
        ax.text(x, y, display_name, fontsize=fontsize,
                ha='center', va='center', color=color,
                fontfamily='sans-serif', fontweight='normal',
                path_effects=[
                    pe.withStroke(linewidth=1.5, foreground='white'),
                ])


def _add_country_outline(ax, linewidth=1.0):
    """Draw a thick country border around Tanzania."""
    country = _get_country_boundary()
    country.boundary.plot(ax=ax, color=COLORS["country_border"],
                          linewidth=linewidth)


def _add_warning_icon(ax, center_x, center_y, icon_size=0.6):
    """Draw a warning triangle icon at the given position."""
    # Triangle with exclamation mark
    triangle = mpatches.RegularPolygon(
        (center_x, center_y), numVertices=3,
        radius=icon_size, orientation=0,
        facecolor='#FFFF00', edgecolor='#000000', linewidth=1.2,
        zorder=10,
    )
    ax.add_patch(triangle)

    # Rain symbol inside triangle (simplified)
    # Small umbrella-like symbol
    ax.text(center_x, center_y - 0.05, '☂', fontsize=8,
            ha='center', va='center', color='black', zorder=11)


def _compute_affected_centroid(gdf, highlight_indices):
    """Compute the centroid of all highlighted polygons combined."""
    if not highlight_indices:
        return None
    affected = gdf.loc[list(highlight_indices)]
    dissolved = affected.dissolve()
    centroid = dissolved.geometry.representative_point().iloc[0]
    return centroid.x, centroid.y


def _draw_user_shapes(ax, drawn_shapes: list, fill_color: str, alpha: float = 0.55):
    """Render user-drawn GeoJSON shapes (polygon, rectangle, circle) on *ax*.

    Each item in *drawn_shapes* is a GeoJSON Feature dict.  Circles are
    stored as Point + ``properties.radius`` (metres).
    """
    if not drawn_shapes:
        return
    from matplotlib.patches import Polygon as MplPoly, Circle as MplCirc
    for feat in drawn_shapes:
        if not isinstance(feat, dict):
            continue
        geom = feat.get("geometry") or feat
        props = feat.get("properties", {})
        gtype = geom.get("type", "")

        if gtype == "Point" and props.get("radius"):
            # Circle — convert radius (metres) to approx degrees
            lng, lat = geom["coordinates"]
            radius_deg = float(props["radius"]) / 111_320
            circ = MplCirc(
                (lng, lat), radius_deg,
                facecolor=fill_color, edgecolor="#000000",
                linewidth=1.5, alpha=alpha, zorder=8,
            )
            ax.add_patch(circ)

        elif gtype in ("Polygon", "MultiPolygon"):
            try:
                shp = shapely_shape(geom)
                polys = [shp] if shp.geom_type == "Polygon" else list(shp.geoms)
                for poly in polys:
                    coords = list(poly.exterior.coords)
                    patch = MplPoly(
                        coords, closed=True,
                        facecolor=fill_color, edgecolor="#000000",
                        linewidth=1.5, alpha=alpha, zorder=8,
                    )
                    ax.add_patch(patch)
            except Exception:
                pass


def generate_region_map(
    highlighted_regions: list[str],
    color: str = "advisory",
    output_path: str = None,
    figsize: tuple = (4.0, 5.0),
    dpi: int = 150,
    title: str = None,
    show_labels: bool = True,
    show_warning_icon: bool = True,
    drawn_shapes: list = None,
) -> str:
    """Generate a Tanzania map with highlighted regions.

    Args:
        highlighted_regions: List of region names to highlight
        color: Color key ("advisory", "warning", "major_warning")
        output_path: Where to save the PNG
        figsize: Figure size in inches
        dpi: Resolution
        title: Optional title
        show_labels: Whether to show region name labels
        show_warning_icon: Whether to show warning triangle icon

    Returns:
        Path to the generated PNG file
    """
    regions = _load_regions()

    fig, ax = plt.subplots(1, 1, figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    # Normalize input names for matching
    highlight_normalized = {_normalize_name(r) for r in highlighted_regions}
    name_map = _build_name_mapping(regions, 'NAME_1')

    # Find matching indices
    highlight_indices = set()
    for norm_name in highlight_normalized:
        if norm_name in name_map:
            highlight_indices.add(name_map[norm_name])

    # Color assignment — when drawn_shapes are provided, keep all regions
    # white so only the drawn shapes show color on the map.
    fill_color = COLORS.get(color, COLORS["advisory"])
    if drawn_shapes:
        region_colors = [COLORS["no_data"]] * len(regions)
    else:
        region_colors = []
        for idx in regions.index:
            if idx in highlight_indices:
                region_colors.append(fill_color)
            else:
                region_colors.append(COLORS["no_data"])

    regions_copy = regions.copy()
    regions_copy['_color'] = region_colors

    # Plot regions — thin black borders matching reference style
    regions_copy.plot(
        ax=ax,
        color=regions_copy['_color'],
        edgecolor="#000000",
        linewidth=0.6,
    )

    # Water bodies clipped to Tanzania boundary
    lw_scale = 1.2 if figsize[0] >= 3.5 else 0.8
    _draw_water_bodies(ax, linewidth_scale=lw_scale)

    # Region name labels
    if show_labels:
        label_size = 4.5 if figsize[0] >= 3.5 else 3.0
        _add_region_labels(ax, regions, fontsize=label_size, color='#000000')

    # Warning icon on affected area
    if show_warning_icon and highlight_indices:
        centroid = _compute_affected_centroid(regions, highlight_indices)
        if centroid:
            icon_r = 0.7 if figsize[0] >= 3.5 else 0.5
            _add_warning_icon(ax, centroid[0], centroid[1], icon_size=icon_r)

    # User-drawn shapes (polygon / circle / rectangle) on top
    if drawn_shapes:
        _draw_user_shapes(ax, drawn_shapes, fill_color, alpha=0.55)

    # Clean up axes
    ax.set_axis_off()
    ax.margins(0.02)

    if title:
        ax.set_title(title, fontsize=7, fontweight='bold', pad=2)

    plt.tight_layout(pad=0.1)

    # Save
    if output_path is None:
        output_path = str(ASSETS_DIR / "placeholders" / "temp_region_map.png")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)

    return output_path


def generate_district_map(
    highlighted_districts: list[str],
    color: str = "advisory",
    output_path: str = None,
    figsize: tuple = (4.0, 5.0),
    dpi: int = 150,
    title: str = None,
    show_labels: bool = True,
    show_warning_icon: bool = False,
    drawn_shapes: list = None,
) -> str:
    """Generate a Tanzania map with highlighted districts.

    Args:
        highlighted_districts: List of district names to highlight
        color: Color key ("advisory", "warning", "major_warning")
        output_path: Where to save the PNG
        figsize: Figure size in inches
        dpi: Resolution
        title: Optional title
        show_labels: Whether to show region name labels
        show_warning_icon: Whether to show warning triangle icon

    Returns:
        Path to the generated PNG file
    """
    districts = _load_districts()
    regions = _load_regions()

    fig, ax = plt.subplots(1, 1, figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    # Normalize input names for matching
    highlight_normalized = {_normalize_name(d) for d in highlighted_districts}
    name_map = _build_name_mapping(districts, 'NAME_2')

    # Find matching indices
    highlight_indices = set()
    for norm_name in highlight_normalized:
        if norm_name in name_map:
            highlight_indices.add(name_map[norm_name])

    # Color assignment — when drawn_shapes are provided, keep all districts
    # white so only the drawn shapes show color on the map.
    fill_color = COLORS.get(color, COLORS["advisory"])
    if drawn_shapes:
        district_colors = [COLORS["no_data"]] * len(districts)
    else:
        district_colors = []
        for idx in districts.index:
            if idx in highlight_indices:
                district_colors.append(fill_color)
            else:
                district_colors.append(COLORS["no_data"])

    districts_copy = districts.copy()
    districts_copy['_color'] = district_colors

    # Plot districts
    districts_copy.plot(
        ax=ax,
        color=districts_copy['_color'],
        edgecolor=COLORS["boundary"],
        linewidth=0.15,
    )

    # Region boundaries on top (black, matching reference)
    regions.boundary.plot(ax=ax, color="#000000", linewidth=0.6)

    # Water bodies clipped to Tanzania
    _draw_water_bodies(ax, linewidth_scale=0.8)

    # Region name labels
    if show_labels:
        label_size = 3.0 if figsize[0] >= 3.0 else 2.5
        _add_region_labels(ax, regions, fontsize=label_size, color='#000000')

    # Add warning icon
    if show_warning_icon and highlight_indices:
        centroid = _compute_affected_centroid(districts, highlight_indices)
        if centroid:
            _add_warning_icon(ax, centroid[0], centroid[1], icon_size=0.5)

    # User-drawn shapes on top
    if drawn_shapes:
        _draw_user_shapes(ax, drawn_shapes, fill_color, alpha=0.55)

    # Clean up axes
    ax.set_axis_off()
    ax.margins(0.02)

    if title:
        ax.set_title(title, fontsize=7, fontweight='bold', pad=2)

    plt.tight_layout(pad=0.1)

    # Save
    if output_path is None:
        output_path = str(ASSETS_DIR / "placeholders" / "temp_district_map.png")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)

    return output_path


def generate_multi_hazard_map(
    advisory_districts: list[str] = None,
    warning_districts: list[str] = None,
    major_warning_districts: list[str] = None,
    output_path: str = None,
    figsize: tuple = (4.5, 6.0),
    dpi: int = 150,
    show_labels: bool = True,
) -> str:
    """Generate a summary map with multiple alert levels shown simultaneously.

    Args:
        advisory_districts: Districts at ADVISORY level
        warning_districts: Districts at WARNING level
        major_warning_districts: Districts at MAJOR WARNING level
        output_path: Where to save the PNG
        show_labels: Whether to show region name labels

    Returns:
        Path to the generated PNG file
    """
    districts = _load_districts()
    regions = _load_regions()

    fig, ax = plt.subplots(1, 1, figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    name_map = _build_name_mapping(districts, 'NAME_2')

    # Build color lookup: major_warning > warning > advisory (priority order)
    idx_colors = {}

    for dist_list, color_key in [
        (advisory_districts or [], "advisory"),
        (warning_districts or [], "warning"),
        (major_warning_districts or [], "major_warning"),
    ]:
        for name in dist_list:
            norm = _normalize_name(name)
            if norm in name_map:
                idx_colors[name_map[norm]] = COLORS[color_key]

    district_colors = []
    for idx in districts.index:
        district_colors.append(idx_colors.get(idx, COLORS["no_data"]))

    districts_copy = districts.copy()
    districts_copy['_color'] = district_colors

    # Plot districts
    districts_copy.plot(
        ax=ax,
        color=districts_copy['_color'],
        edgecolor=COLORS["boundary"],
        linewidth=0.15,
    )

    # Region boundaries on top (black, matching reference)
    regions.boundary.plot(ax=ax, color="#000000", linewidth=0.6)

    # Water bodies clipped to Tanzania
    _draw_water_bodies(ax, linewidth_scale=0.8)

    # Region labels
    if show_labels:
        label_size = 3.5 if figsize[0] >= 3.0 else 2.5
        _add_region_labels(ax, regions, fontsize=label_size, color='#000000')

    ax.set_axis_off()
    ax.margins(0.02)
    plt.tight_layout(pad=0.1)

    if output_path is None:
        output_path = str(ASSETS_DIR / "placeholders" / "temp_summary_map.png")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)

    return output_path
