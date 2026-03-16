"""Auto-generates maps for bulletins based on input data.

Instead of requiring pre-made map images, this module generates maps
from district/region lists in the bulletin data.
"""

from pathlib import Path
from typing import Optional

from ..models.common import HazardType, AlertLevel
from ..models.seven22e4 import Seven22E4Bulletin, FiveDayEntry
from ..models.multirisk import MultiriskBulletin, MultiriskDayForecast, DaySummary
from .map_generator import generate_region_map, generate_district_map, generate_multi_hazard_map

OUTPUT_MAP_DIR = Path(__file__).parent.parent.parent / "output" / "maps"


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def generate_722e4_maps(bulletin: Seven22E4Bulletin) -> dict:
    """Generate maps for all days of a 722E_4 bulletin.

    Returns dict mapping day_index -> map_path.
    """
    _ensure_dir(OUTPUT_MAP_DIR)
    maps = {}

    date_str = bulletin.issue_date.strftime("%Y%m%d")

    for i, day in enumerate(bulletin.days):
        # Day 1 gets a larger map (landscape); Days 2-5 get medium maps
        if i == 0:
            fig_sz, fig_dpi = (5.5, 4.5), 200
        else:
            fig_sz, fig_dpi = (3.5, 3.2), 200

        if day.is_no_warning:
            # Still generate a blank Tanzania map for NO WARNING days
            path = generate_region_map(
                highlighted_regions=[],
                color="advisory",
                output_path=str(OUTPUT_MAP_DIR / f"722e4_{date_str}_day{i+1}.png"),
                figsize=fig_sz,
                dpi=fig_dpi,
            )
        else:
            # Collect all regions from hazard descriptions
            regions = _extract_regions_from_722e4_day(day)
            alert_color = _get_alert_color(day.max_alert_level)
            # Collect drawn shapes from all hazards in this day
            day_shapes = []
            for h in day.hazards:
                if hasattr(h, "drawn_shapes") and h.drawn_shapes:
                    day_shapes.extend(h.drawn_shapes)
            path = generate_region_map(
                highlighted_regions=regions,
                color=alert_color,
                output_path=str(OUTPUT_MAP_DIR / f"722e4_{date_str}_day{i+1}.png"),
                figsize=fig_sz,
                dpi=fig_dpi,
                drawn_shapes=day_shapes or None,
            )
        maps[i] = path

    return maps


def _extract_regions_from_722e4_day(day: FiveDayEntry) -> list[str]:
    """Extract region names from hazard descriptions.

    For auto-map generation, we look at the 'regions' field if available,
    or try to parse from description text.
    """
    regions = set()
    for hazard in day.hazards:
        # Check if the hazard has explicit regions (added by input)
        if hasattr(hazard, 'regions') and hazard.regions:
            regions.update(hazard.regions)
    return list(regions)


def _get_alert_color(level: AlertLevel) -> str:
    mapping = {
        AlertLevel.ADVISORY: "advisory",
        AlertLevel.WARNING: "warning",
        AlertLevel.MAJOR_WARNING: "major_warning",
        AlertLevel.NO_WARNING: "advisory",
    }
    return mapping.get(level, "advisory")


def generate_multirisk_maps(bulletin: MultiriskBulletin) -> dict:
    """Generate all maps for a Multirisk bulletin.

    Returns dict with keys like:
        'day1_heavy_rain', 'day1_large_waves', 'day1_strong_wind', 'day1_floods',
        'day1_summary', 'day2_heavy_rain', etc.
    """
    _ensure_dir(OUTPUT_MAP_DIR)
    maps = {}

    num = bulletin.bulletin_number
    date_str = bulletin.issue_date.strftime("%Y%m%d")

    for day in bulletin.days:
        dn = day.day_number

        # Find the matching day summary for district lists
        day_summary = None
        for ds in bulletin.day_summaries:
            if ds.day_number == dn:
                day_summary = ds
                break

        advisory_districts = day_summary.advisory_districts if day_summary else []
        warning_districts = day_summary.warning_districts if day_summary else []
        major_districts = day_summary.major_warning_districts if day_summary else []

        all_affected = advisory_districts + warning_districts + major_districts

        # Generate hazard-specific maps
        # For each hazard type, we color the districts
        for hazard_type in [HazardType.HEAVY_RAIN, HazardType.LARGE_WAVES,
                           HazardType.STRONG_WIND, HazardType.FLOODS]:
            key = f"day{dn}_{hazard_type.value.lower()}"

            # Determine which districts to highlight for this hazard
            # In the original bulletins, each hazard map shows different regions
            # For now, use the full district list for all hazards that have panels
            has_panel = any(
                hp.hazard_type == hazard_type for hp in day.hazard_panels
            )

            if has_panel and all_affected:
                path = generate_district_map(
                    highlighted_districts=all_affected,
                    color="advisory",  # Most common
                    output_path=str(OUTPUT_MAP_DIR / f"mr_{num}_{date_str}_{key}.png"),
                    figsize=(3.0, 4.0),
                    dpi=150,
                )
            else:
                # Generate blank map for this hazard
                path = generate_district_map(
                    highlighted_districts=[],
                    color="advisory",
                    output_path=str(OUTPUT_MAP_DIR / f"mr_{num}_{date_str}_{key}.png"),
                    figsize=(3.0, 4.0),
                    dpi=150,
                )
            maps[key] = path

        # Generate summary map
        summary_key = f"day{dn}_summary"
        path = generate_multi_hazard_map(
            advisory_districts=advisory_districts,
            warning_districts=warning_districts,
            major_warning_districts=major_districts,
            output_path=str(OUTPUT_MAP_DIR / f"mr_{num}_{date_str}_{summary_key}.png"),
            figsize=(4.5, 6.0),
            dpi=150,
        )
        maps[summary_key] = path

    return maps
