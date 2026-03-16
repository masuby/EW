"""TCVMP Bridge — Live connection to TCVMP PostGIS database.

Replicates the exact TCVMP analysis capabilities inside the EW dashboard:
  - Infrastructure Exposure: facility counts per district by PHC 2022 Census
  - Flood Risk Assessment: EAD (Expected Annual Damage), flood depth per RP
  - Spatial Analysis: climate indicator exposure (temperature, flood, drought, landslide)
  - Admin Risk Summaries: aggregated risk/exposure per district
  - Overlay Layers: available map layers from TCVMP catalogue

Connection: docker exec → g3w-suite container → PostGIS at 192.168.0.1:5435
Database: g3wsuite (PostGIS-enabled)
"""

import json
import subprocess
import logging
from functools import lru_cache

import streamlit as st

logger = logging.getLogger(__name__)

# ── TCVMP database access via docker ───────────────────────────────
_DOCKER_CONTAINER = "g3w-suite-docker-g3w-suite-1"
_PG_HOST = "192.168.0.1"
_PG_PORT = "5435"
_PG_USER = "g3wsuite"
_PG_PASS = "g3wsuite123"
_PG_DB = "g3wsuite"

# ── Facility layer configs ─────────────────────────────────────────
FACILITY_LAYERS = {
    "phc_health_facilities": {
        "label": "Health Facilities",
        "icon": "hospital",
        "color": "#E53935",
        "name_col": "b0102b_nam",
        "region_col": "region_name",
        "district_col": "district_name",
        "lat_col": "b0301_lati",
        "lon_col": "b0301_long",
    },
    "phc_education_facilities": {
        "label": "Education Facilities",
        "icon": "school",
        "color": "#1E88E5",
        "name_col": "name",
        "region_col": "region_",
        "district_col": "district",
        "lat_col": "b0301_lati",
        "lon_col": "b0301_long",
    },
    "phc_water_facilities": {
        "label": "Water Facilities",
        "icon": "water",
        "color": "#00ACC1",
        "name_col": "ea_name",
        "region_col": "region_nam",
        "district_col": "district_n",
        "lat_col": "latitude",
        "lon_col": "longitude",
    },
    "phc_markets": {
        "label": "Markets",
        "icon": "shop",
        "color": "#F57C00",
        "name_col": "name",
        "region_col": "region_nam",
        "district_col": "district_n",
        "lat_col": "latitude",
        "lon_col": "longitude",
    },
    "phc_government_offices": {
        "label": "Government Offices",
        "icon": "building",
        "color": "#5E35B1",
        "name_col": "offices",
        "region_col": "b_region_n",
        "district_col": "b_district",
        "lat_col": "b_latitude",
        "lon_col": "b_longitud",
    },
    "airports": {
        "label": "Airports",
        "icon": "plane",
        "color": "#6D4C41",
        "name_col": "name",
        "region_col": None,
        "district_col": None,
        "lat_col": None,
        "lon_col": None,
        "geom_col": "geom",
    },
    "sea_ports": {
        "label": "Sea Ports",
        "icon": "ship",
        "color": "#0277BD",
        "name_col": "name",
        "region_col": None,
        "district_col": None,
        "lat_col": None,
        "lon_col": None,
        "geom_col": "geom",
    },
    "populated_places": {
        "label": "Populated Places",
        "icon": "people",
        "color": "#455A64",
        "name_col": "name",
        "region_col": None,
        "district_col": None,
        "lat_col": None,
        "lon_col": None,
        "geom_col": "geom",
    },
}

DEFAULT_ANALYSIS_LAYERS = [
    "phc_health_facilities",
    "phc_education_facilities",
    "phc_water_facilities",
    "phc_markets",
]


# ═══════════════════════════════════════════════════════════════════
# SQL EXECUTION
# ═══════════════════════════════════════════════════════════════════

def _run_sql(sql: str, timeout: int = 15) -> str | None:
    """Execute SQL on TCVMP PostGIS via docker exec. Returns raw output."""
    cmd = [
        "docker", "exec", _DOCKER_CONTAINER, "bash", "-c",
        f'PGPASSWORD={_PG_PASS} psql -h {_PG_HOST} -p {_PG_PORT} '
        f'-U {_PG_USER} -d {_PG_DB} -t -A -F "|" -c "{sql}"'
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            logger.error("TCVMP SQL error: %s", result.stderr[:300])
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error("TCVMP query timed out after %ds", timeout)
        return None
    except FileNotFoundError:
        logger.error("Docker not available")
        return None


def is_tcvmp_available() -> bool:
    """Check if the TCVMP database is reachable."""
    output = _run_sql("SELECT 1", timeout=5)
    return output is not None and "1" in output


def _parse_rows(output: str) -> list[list[str]]:
    """Parse pipe-delimited SQL output into list of rows."""
    if not output:
        return []
    rows = []
    for line in output.strip().split("\n"):
        if line.strip():
            rows.append([c.strip() for c in line.split("|")])
    return rows


def _in_clause(names: list[str]) -> str:
    """Build SQL IN clause from list of names."""
    escaped = [n.replace("'", "''") for n in names]
    return ",".join(f"'{n}'" for n in escaped)


# ═══════════════════════════════════════════════════════════════════
# 1. INFRASTRUCTURE EXPOSURE (facility counts per district)
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_district_facility_counts(districts: tuple, layers: tuple = None) -> dict:
    """Query TCVMP for facility counts per district.

    Returns: {table: {district: count}, "_totals": {district: count}}
    """
    districts = list(districts)
    layers = list(layers) if layers else DEFAULT_ANALYSIS_LAYERS
    if not districts:
        return {}

    result = {}
    totals = {}

    for table in layers:
        config = FACILITY_LAYERS.get(table)
        if not config or not config.get("district_col"):
            continue

        district_col = config["district_col"]
        sql = (
            f"SELECT {district_col}, count(*) "
            f"FROM {table} "
            f"WHERE {district_col} IN ({_in_clause(districts)}) "
            f"GROUP BY {district_col} ORDER BY count(*) DESC"
        )
        output = _run_sql(sql)
        if not output:
            continue

        counts = {}
        for row in _parse_rows(output):
            if len(row) >= 2 and row[1].isdigit():
                counts[row[0]] = int(row[1])
                totals[row[0]] = totals.get(row[0], 0) + int(row[1])
        result[table] = counts

    result["_totals"] = totals
    return result


@st.cache_data(ttl=300)
def get_exposure_summary(districts_by_tier: dict, layers: tuple = None) -> dict:
    """Get exposure summary for districts grouped by alert tier."""
    layers = tuple(layers) if layers else tuple(DEFAULT_ANALYSIS_LAYERS)
    all_districts = []
    for tier_districts in districts_by_tier.values():
        all_districts.extend(tier_districts)
    if not all_districts:
        return {}

    counts = get_district_facility_counts(tuple(set(all_districts)), layers)

    result = {}
    grand_total = 0
    for tier_key, tier_districts in districts_by_tier.items():
        tier_data = {"total_facilities": 0, "by_type": {}, "districts": tier_districts}
        for table in layers:
            config = FACILITY_LAYERS.get(table, {})
            label = config.get("label", table)
            table_counts = counts.get(table, {})
            tier_count = sum(table_counts.get(d, 0) for d in tier_districts)
            tier_data["by_type"][label] = tier_count
            tier_data["total_facilities"] += tier_count
        grand_total += tier_data["total_facilities"]
        result[tier_key] = tier_data

    result["grand_total"] = grand_total
    return result


@st.cache_data(ttl=300)
def get_facility_points(districts: tuple, table: str,
                        limit: int = 500) -> list[dict]:
    """Get facility point locations for map overlay."""
    config = FACILITY_LAYERS.get(table)
    if not config or not districts:
        return []
    districts = list(districts)

    name_col = config.get("name_col", "''")
    district_col = config.get("district_col")
    lat_col = config.get("lat_col")
    lon_col = config.get("lon_col")

    if district_col and lat_col and lon_col:
        sql = (
            f"SELECT COALESCE({name_col}::text,''), {lat_col}, {lon_col}, "
            f"COALESCE({district_col}::text,'') "
            f"FROM {table} "
            f"WHERE {district_col} IN ({_in_clause(districts)}) "
            f"AND {lat_col} IS NOT NULL AND {lon_col} IS NOT NULL "
            f"LIMIT {limit}"
        )
    elif config.get("geom_col"):
        geom_col = config["geom_col"]
        sql = (
            f"SELECT COALESCE({name_col}::text,''), "
            f"ST_Y(ST_Centroid({geom_col})), ST_X(ST_Centroid({geom_col})), '' "
            f"FROM {table} WHERE {geom_col} IS NOT NULL LIMIT {limit}"
        )
    else:
        return []

    output = _run_sql(sql, timeout=20)
    if not output:
        return []

    points = []
    for row in _parse_rows(output):
        if len(row) >= 3:
            try:
                points.append({
                    "name": row[0],
                    "lat": float(row[1]),
                    "lon": float(row[2]),
                    "district": row[3] if len(row) > 3 else "",
                })
            except (ValueError, IndexError):
                continue
    return points


# ═══════════════════════════════════════════════════════════════════
# 2. FLOOD RISK ASSESSMENT (from gca_facilityriskresult)
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_flood_risk_by_district(districts: tuple) -> list[dict]:
    """Get flood risk summary per district from gca_adminrisksummary.

    Returns list of dicts with: district, facility_count, ead_baseline,
    ead_future, ead_change, avg_depth_b_rp100, avg_depth_f_rp100, max_facility
    """
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT admin_name, facility_count, "
        "round(total_ead_baseline::numeric,2), "
        "round(total_ead_future::numeric,2), "
        "round(total_ead_change::numeric,2), "
        "round(avg_depth_b_rp100::numeric,4), "
        "round(avg_depth_f_rp100::numeric,4), "
        "max_ead_facility "
        "FROM gca_adminrisksummary "
        f"WHERE admin_level='district' AND admin_name IN ({_in_clause(districts)}) "
        "AND project_id = (SELECT max(id) FROM gca_riskassessmentproject WHERE status='complete' AND exposure_table='phc_health_facilities') "
        "ORDER BY total_ead_future DESC"
    )
    output = _run_sql(sql, timeout=20)
    if not output:
        return []

    results = []
    seen = set()  # deduplicate (multiple project_ids)
    for row in _parse_rows(output):
        if len(row) >= 7 and row[0] not in seen:
            seen.add(row[0])
            try:
                results.append({
                    "district": row[0],
                    "facility_count": int(row[1]),
                    "ead_baseline": float(row[2]),
                    "ead_future": float(row[3]),
                    "ead_change": float(row[4]),
                    "depth_b_rp100": float(row[5]),
                    "depth_f_rp100": float(row[6]),
                    "max_facility": row[7] if len(row) > 7 else "",
                })
            except (ValueError, IndexError):
                continue
    return results


@st.cache_data(ttl=300)
def get_flood_risk_facilities(districts: tuple, limit: int = 50) -> list[dict]:
    """Get top facilities by flood risk (EAD) in given districts.

    Returns list of: facility_name, district, ead_baseline, ead_future,
    ead_change_pct, depth_b_rp100, depth_f_rp100
    """
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT facility_name, district, "
        "round(ead_baseline::numeric,2), round(ead_future::numeric,2), "
        "round(ead_change_pct::numeric,1), "
        "round(depth_b_rp100::numeric,3), round(depth_f_rp100::numeric,3) "
        "FROM gca_facilityriskresult "
        f"WHERE district IN ({_in_clause(districts)}) AND ead_future > 0 "
        "AND project_id = (SELECT max(id) FROM gca_riskassessmentproject WHERE status='complete' AND exposure_table='phc_health_facilities') "
        f"ORDER BY ead_future DESC LIMIT {limit}"
    )
    output = _run_sql(sql, timeout=30)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 7:
            try:
                results.append({
                    "name": row[0],
                    "district": row[1],
                    "ead_baseline": float(row[2]),
                    "ead_future": float(row[3]),
                    "ead_change_pct": float(row[4]) if row[4] else 0,
                    "depth_b_rp100": float(row[5]),
                    "depth_f_rp100": float(row[6]),
                })
            except (ValueError, IndexError):
                continue
    return results


@st.cache_data(ttl=300)
def get_flood_risk_totals(districts: tuple) -> dict:
    """Get aggregate flood risk totals for a set of districts.

    Returns: {total_facilities, total_ead_baseline, total_ead_future,
              total_ead_change, exposed_count}
    """
    districts = list(districts)
    if not districts:
        return {}

    sql = (
        "SELECT count(*), "
        "round(sum(ead_baseline)::numeric,2), round(sum(ead_future)::numeric,2), "
        "round(sum(ead_future - ead_baseline)::numeric,2), "
        "count(CASE WHEN depth_f_rp100 > 0 THEN 1 END) "
        "FROM gca_facilityriskresult "
        f"WHERE district IN ({_in_clause(districts)}) "
        "AND project_id = (SELECT max(id) FROM gca_riskassessmentproject WHERE status='complete' AND exposure_table='phc_health_facilities')"
    )
    output = _run_sql(sql, timeout=20)
    if not output:
        return {}

    rows = _parse_rows(output)
    if not rows or len(rows[0]) < 5:
        return {}

    row = rows[0]
    try:
        return {
            "total_facilities": int(row[0]),
            "total_ead_baseline": float(row[1]) if row[1] else 0,
            "total_ead_future": float(row[2]) if row[2] else 0,
            "total_ead_change": float(row[3]) if row[3] else 0,
            "exposed_count": int(row[4]) if row[4] else 0,
        }
    except (ValueError, IndexError):
        return {}


# ═══════════════════════════════════════════════════════════════════
# 3. SPATIAL ANALYSIS (climate exposure from gca_spatialanalysis*)
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def get_available_analyses() -> list[dict]:
    """Get completed spatial analysis runs with their indicator info.

    Returns list of: {run_id, indicator, category, scenario, analysis_type,
                      overlay_table, result_count}
    """
    sql = (
        "SELECT r.id, i.name, i.category, s.name, "
        "r.analysis_type, r.overlay_table, "
        "(SELECT count(*) FROM gca_spatialanalysisresult sr WHERE sr.run_id=r.id) "
        "FROM gca_spatialanalysisrun r "
        "JOIN gca_climatescenariolayer l ON r.indicator_layer_id=l.id "
        "JOIN gca_indicator i ON l.indicator_id=i.id "
        "JOIN gca_climatescenario s ON l.scenario_id=s.id "
        "WHERE r.status='complete' "
        "ORDER BY r.id DESC"
    )
    output = _run_sql(sql, timeout=15)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 7:
            try:
                results.append({
                    "run_id": int(row[0]),
                    "indicator": row[1],
                    "category": row[2],
                    "scenario": row[3],
                    "analysis_type": row[4],
                    "overlay_table": row[5],
                    "result_count": int(row[6]),
                })
            except (ValueError, IndexError):
                continue
    return results


@st.cache_data(ttl=300)
def get_spatial_exposure_summary(districts: tuple) -> list[dict]:
    """Get spatial analysis admin summaries for given districts.

    Pulls from gca_spatialanalysisadminsummary joined with run/indicator info.
    Returns list of: {district, indicator, category, scenario, feature_count,
                      exposed_count, value_min, value_max, value_mean}
    """
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT s.admin_name, i.name, i.category, sc.name, "
        "s.feature_count, s.exposed_count, "
        "round(s.value_min::numeric,3), round(s.value_max::numeric,3), "
        "round(s.value_mean::numeric,3) "
        "FROM gca_spatialanalysisadminsummary s "
        "JOIN gca_spatialanalysisrun r ON s.run_id=r.id "
        "JOIN gca_climatescenariolayer l ON r.indicator_layer_id=l.id "
        "JOIN gca_indicator i ON l.indicator_id=i.id "
        "JOIN gca_climatescenario sc ON l.scenario_id=sc.id "
        f"WHERE s.admin_level='district' AND s.admin_name IN ({_in_clause(districts)}) "
        "ORDER BY i.category, i.name, s.admin_name"
    )
    output = _run_sql(sql, timeout=30)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 9:
            try:
                results.append({
                    "district": row[0],
                    "indicator": row[1],
                    "category": row[2],
                    "scenario": row[3],
                    "feature_count": int(row[4]),
                    "exposed_count": int(row[5]),
                    "value_min": float(row[6]) if row[6] else 0,
                    "value_max": float(row[7]) if row[7] else 0,
                    "value_mean": float(row[8]) if row[8] else 0,
                })
            except (ValueError, IndexError):
                continue
    return results


@st.cache_data(ttl=600)
def get_overlay_layers() -> list[dict]:
    """Get available overlay layers from TCVMP catalogue.

    Returns list of: {id, name, category_id, layer_type, source_type}
    """
    sql = (
        "SELECT id, name, category_id, layer_type, source_type "
        "FROM gca_overlaylayer ORDER BY category_id, name"
    )
    output = _run_sql(sql, timeout=10)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 5:
            try:
                results.append({
                    "id": int(row[0]),
                    "name": row[1],
                    "category_id": int(row[2]) if row[2] else 0,
                    "layer_type": row[3],
                    "source_type": row[4],
                })
            except (ValueError, IndexError):
                continue
    return results


# ═══════════════════════════════════════════════════════════════════
# 4. STREAMLIT UI RENDERERS
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# 5. POPULATION AT RISK (from populated_places + district geometry)
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_population_at_risk(districts: tuple) -> dict:
    """Estimate population in affected districts using populated_places.

    Returns: {total_pop, settlements, by_district: {name: {pop, settlements}}}
    """
    districts = list(districts)
    if not districts:
        return {}

    # Join populated_places with district boundaries
    sql = (
        "SELECT d.dist_name, count(p.ogc_fid), "
        "coalesce(sum(p.population::bigint),0) "
        "FROM phc_districts d "
        "JOIN populated_places p ON ST_Within(p.geom, d.shape) "
        f"WHERE d.dist_name IN ({_in_clause(districts)}) "
        "AND p.population IS NOT NULL AND p.population ~ '^[0-9]+$' "
        "GROUP BY d.dist_name ORDER BY sum(p.population::bigint) DESC"
    )
    output = _run_sql(sql, timeout=30)
    if not output:
        return {}

    by_district = {}
    total_pop = 0
    total_settlements = 0
    for row in _parse_rows(output):
        if len(row) >= 3:
            try:
                name = row[0]
                settlements = int(row[1])
                pop = int(row[2])
                by_district[name] = {"population": pop, "settlements": settlements}
                total_pop += pop
                total_settlements += settlements
            except (ValueError, IndexError):
                continue

    return {
        "total_population": total_pop,
        "total_settlements": total_settlements,
        "by_district": by_district,
    }


# ═══════════════════════════════════════════════════════════════════
# 6. FACILITY TYPE BREAKDOWN (education, water types)
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_education_type_breakdown(districts: tuple) -> list[dict]:
    """Get education facility counts by type in affected districts."""
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT type, count(*) FROM phc_education_facilities "
        f"WHERE district IN ({_in_clause(districts)}) "
        "AND type IS NOT NULL "
        "GROUP BY type ORDER BY count(*) DESC"
    )
    output = _run_sql(sql, timeout=15)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 2:
            try:
                results.append({"type": row[0], "count": int(row[1])})
            except (ValueError, IndexError):
                continue
    return results


@st.cache_data(ttl=300)
def get_water_type_breakdown(districts: tuple) -> list[dict]:
    """Get water facility counts by type in affected districts."""
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT type, count(*) FROM phc_water_facilities "
        f"WHERE district_n IN ({_in_clause(districts)}) "
        "AND type IS NOT NULL "
        "GROUP BY type ORDER BY count(*) DESC"
    )
    output = _run_sql(sql, timeout=15)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 2:
            try:
                results.append({"type": row[0], "count": int(row[1])})
            except (ValueError, IndexError):
                continue
    return results


# ═══════════════════════════════════════════════════════════════════
# 7. FLOOD DEPTH DISTRIBUTION (for charts)
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_flood_depth_distribution(districts: tuple) -> list[dict]:
    """Get flood depth distribution for histogram chart.

    Returns depth ranges and facility counts in each range.
    """
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT "
        "CASE "
        "  WHEN depth_f_rp100 = 0 THEN 'No flood' "
        "  WHEN depth_f_rp100 <= 0.3 THEN '0-0.3m' "
        "  WHEN depth_f_rp100 <= 1.0 THEN '0.3-1m' "
        "  WHEN depth_f_rp100 <= 3.0 THEN '1-3m' "
        "  WHEN depth_f_rp100 <= 6.0 THEN '3-6m' "
        "  ELSE '>6m' "
        "END as depth_range, "
        "count(*) "
        "FROM gca_facilityriskresult "
        f"WHERE district IN ({_in_clause(districts)}) "
        "AND project_id = (SELECT max(id) FROM gca_riskassessmentproject "
        "WHERE status='complete' AND exposure_table='phc_health_facilities') "
        "GROUP BY depth_range ORDER BY min(depth_f_rp100)"
    )
    output = _run_sql(sql, timeout=20)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 2:
            try:
                results.append({"range": row[0], "count": int(row[1])})
            except (ValueError, IndexError):
                continue
    return results


@st.cache_data(ttl=300)
def get_flood_ead_by_district(districts: tuple) -> list[dict]:
    """Get EAD baseline vs future per district for comparison chart."""
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT admin_name, "
        "round(total_ead_baseline::numeric, 0), "
        "round(total_ead_future::numeric, 0), "
        "round(total_ead_change::numeric, 0), "
        "facility_count "
        "FROM gca_adminrisksummary "
        f"WHERE admin_level='district' AND admin_name IN ({_in_clause(districts)}) "
        "AND project_id = (SELECT max(id) FROM gca_riskassessmentproject "
        "WHERE status='complete' AND exposure_table='phc_health_facilities') "
        "AND total_ead_future > 0 "
        "ORDER BY total_ead_future DESC LIMIT 15"
    )
    output = _run_sql(sql, timeout=15)
    if not output:
        return []

    results = []
    seen = set()
    for row in _parse_rows(output):
        if len(row) >= 5 and row[0] not in seen:
            seen.add(row[0])
            try:
                results.append({
                    "district": row[0],
                    "ead_baseline": float(row[1]),
                    "ead_future": float(row[2]),
                    "ead_change": float(row[3]),
                    "facility_count": int(row[4]),
                })
            except (ValueError, IndexError):
                continue
    return results


# ═══════════════════════════════════════════════════════════════════
# 8. CLIMATE INDICATORS SUMMARY
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_climate_indicators_for_districts(districts: tuple) -> list[dict]:
    """Get all climate indicator summaries for affected districts.

    Returns aggregated data per indicator with min/max/mean across districts.
    """
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT r.indicator_abbreviation, r.indicator_unit, "
        "r.scenario_name, r.timeslice_name, r.datatype_name, "
        "count(DISTINCT s.admin_name) as n_districts, "
        "sum(s.feature_count) as total_features, "
        "sum(s.exposed_count) as total_exposed, "
        "round(min(s.value_min)::numeric, 3), "
        "round(max(s.value_max)::numeric, 3), "
        "round(avg(s.value_mean)::numeric, 3) "
        "FROM gca_spatialanalysisadminsummary s "
        "JOIN gca_spatialanalysisrun r ON s.run_id = r.id "
        f"WHERE s.admin_level='district' AND s.admin_name IN ({_in_clause(districts)}) "
        "AND r.status='complete' "
        "GROUP BY r.indicator_abbreviation, r.indicator_unit, "
        "r.scenario_name, r.timeslice_name, r.datatype_name "
        "ORDER BY r.indicator_abbreviation"
    )
    output = _run_sql(sql, timeout=30)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 11:
            try:
                total_f = int(row[6])
                total_e = int(row[7])
                results.append({
                    "indicator": row[0],
                    "unit": row[1],
                    "scenario": row[2],
                    "timeslice": row[3],
                    "datatype": row[4],
                    "n_districts": int(row[5]),
                    "total_features": total_f,
                    "total_exposed": total_e,
                    "exposure_pct": round(total_e / total_f * 100, 1) if total_f > 0 else 0,
                    "value_min": float(row[8]) if row[8] else 0,
                    "value_max": float(row[9]) if row[9] else 0,
                    "value_mean": float(row[10]) if row[10] else 0,
                })
            except (ValueError, IndexError):
                continue
    return results


# ═══════════════════════════════════════════════════════════════════
# 9. ROAD & TRANSPORT NETWORK
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def get_roads_in_districts(districts: tuple) -> list[dict]:
    """Get primary road segments that intersect affected districts."""
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT r.name, r.highway, r.surface, "
        "round(ST_Length(r.geom::geography)::numeric/1000, 2) as km, "
        "ST_AsGeoJSON(r.geom) "
        "FROM roads_primary r "
        "JOIN phc_districts d ON ST_Intersects(r.geom, d.shape) "
        f"WHERE d.dist_name IN ({_in_clause(districts)}) "
        "GROUP BY r.ogc_fid, r.name, r.highway, r.surface, r.geom "
        "ORDER BY km DESC LIMIT 100"
    )
    output = _run_sql(sql, timeout=30)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 5:
            try:
                results.append({
                    "name": row[0] or "Unnamed",
                    "type": row[1],
                    "surface": row[2] or "unknown",
                    "km": float(row[3]),
                    "geojson": row[4],
                })
            except (ValueError, IndexError):
                continue
    return results


@st.cache_data(ttl=600)
def get_road_km_summary(districts: tuple) -> dict:
    """Get total road km by type in affected districts."""
    districts = list(districts)
    if not districts:
        return {}

    sql = (
        "SELECT r.highway, "
        "round(sum(ST_Length(r.geom::geography))::numeric/1000, 1) as total_km, "
        "count(DISTINCT r.ogc_fid) as segments "
        "FROM roads_primary r "
        "JOIN phc_districts d ON ST_Intersects(r.geom, d.shape) "
        f"WHERE d.dist_name IN ({_in_clause(districts)}) "
        "GROUP BY r.highway ORDER BY total_km DESC"
    )
    output = _run_sql(sql, timeout=30)
    if not output:
        return {}

    result = {}
    for row in _parse_rows(output):
        if len(row) >= 3:
            try:
                result[row[0]] = {
                    "km": float(row[1]),
                    "segments": int(row[2]),
                }
            except (ValueError, IndexError):
                continue
    return result


@st.cache_data(ttl=600)
def get_railway_summary(districts: tuple) -> dict:
    """Get railway segments intersecting affected districts."""
    districts = list(districts)
    if not districts:
        return {}

    sql = (
        "SELECT "
        "count(DISTINCT r.ogc_fid) as segments, "
        "round(sum(ST_Length(r.geom::geography))::numeric/1000, 1) as total_km "
        "FROM railways r "
        "JOIN phc_districts d ON ST_Intersects(r.geom, d.shape) "
        f"WHERE d.dist_name IN ({_in_clause(districts)})"
    )
    output = _run_sql(sql, timeout=20)
    if not output:
        return {}

    rows = _parse_rows(output)
    if rows and len(rows[0]) >= 2:
        try:
            return {
                "segments": int(rows[0][0]),
                "km": float(rows[0][1]) if rows[0][1] else 0,
            }
        except (ValueError, IndexError):
            pass
    return {}


# ═══════════════════════════════════════════════════════════════════
# 10. TOP RISK FACILITIES WITH COORDINATES (for map hotspots)
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_flood_risk_hotspots(districts: tuple, limit: int = 30) -> list[dict]:
    """Get top flood-risk facilities with coordinates for map overlay."""
    districts = list(districts)
    if not districts:
        return []

    sql = (
        "SELECT facility_name, district, region, "
        "round(ead_future::numeric, 0), "
        "round(depth_f_rp100::numeric, 2), "
        "round(damage_f_rp100::numeric, 0), "
        "ST_Y(geom), ST_X(geom) "
        "FROM gca_facilityriskresult "
        f"WHERE district IN ({_in_clause(districts)}) "
        "AND ead_future > 0 AND geom IS NOT NULL "
        "AND project_id = (SELECT max(id) FROM gca_riskassessmentproject "
        "WHERE status='complete' AND exposure_table='phc_health_facilities') "
        f"ORDER BY ead_future DESC LIMIT {limit}"
    )
    output = _run_sql(sql, timeout=20)
    if not output:
        return []

    results = []
    for row in _parse_rows(output):
        if len(row) >= 8:
            try:
                results.append({
                    "name": row[0],
                    "district": row[1],
                    "region": row[2],
                    "ead": float(row[3]),
                    "depth": float(row[4]),
                    "damage": float(row[5]),
                    "lat": float(row[6]),
                    "lon": float(row[7]),
                })
            except (ValueError, IndexError):
                continue
    return results


# ═══════════════════════════════════════════════════════════════════
# STREAMLIT UI RENDERERS
# ═══════════════════════════════════════════════════════════════════

_TIER_STYLE = {
    "major_warning": ("#FF0000", "#FFF", "Major Warning"),
    "warning": ("#FFA500", "#FFF", "Warning"),
    "advisory": ("#FFFF00", "#000", "Advisory"),
}


def render_exposure_analysis(districts_by_tier: dict,
                             key_prefix: str = "exposure"):
    """Render infrastructure exposure panel — facility counts by tier."""
    if not is_tcvmp_available():
        st.warning("TCVMP database not available.")
        return

    all_districts = []
    for dists in districts_by_tier.values():
        all_districts.extend(dists)
    if not all_districts:
        st.caption("No districts selected.")
        return

    with st.spinner("Querying TCVMP infrastructure data..."):
        summary = get_exposure_summary(districts_by_tier)

    if not summary or summary.get("grand_total", 0) == 0:
        st.caption("No facility data found for selected districts.")
        return

    st.metric("Total Facilities at Risk", f"{summary['grand_total']:,}")

    for tier_key in ["major_warning", "warning", "advisory"]:
        tier_data = summary.get(tier_key)
        if not tier_data or tier_data["total_facilities"] == 0:
            continue
        bg, tc, label = _TIER_STYLE[tier_key]
        n_d = len(tier_data["districts"])
        n_f = tier_data["total_facilities"]
        st.markdown(
            f'<div style="background:{bg};color:{tc};padding:8px 14px;'
            f'border-radius:6px;margin:6px 0;font-size:13px;">'
            f'<b>{label}</b> — {n_d} district(s), {n_f:,} facilities</div>',
            unsafe_allow_html=True,
        )
        by_type = tier_data.get("by_type", {})
        if by_type:
            cols = st.columns(min(len(by_type), 4))
            for i, (ftype, count) in enumerate(
                sorted(by_type.items(), key=lambda x: -x[1])
            ):
                if count > 0:
                    with cols[i % len(cols)]:
                        st.metric(ftype, f"{count:,}")


def render_flood_risk_panel(districts: list[str], key_prefix: str = "flood"):
    """Render flood risk assessment panel — EAD, depth, damage per district.

    Matches TCVMP risk assessment view.
    """
    if not districts:
        st.caption("No districts selected.")
        return

    with st.spinner("Querying TCVMP flood risk data..."):
        totals = get_flood_risk_totals(tuple(sorted(districts)))
        district_risk = get_flood_risk_by_district(tuple(sorted(districts)))

    if not totals or totals.get("total_facilities", 0) == 0:
        st.caption("No flood risk data available for these districts.")
        return

    # ── Summary metrics ──
    mcols = st.columns(4)
    with mcols[0]:
        st.metric("Facilities Assessed", f"{totals['total_facilities']:,}")
    with mcols[1]:
        st.metric("Exposed (RP100)",
                   f"{totals['exposed_count']:,}")
    with mcols[2]:
        ead_f = totals.get("total_ead_future", 0)
        if ead_f >= 1_000_000:
            st.metric("EAD Future", f"TZS {ead_f/1_000_000:.1f}M")
        elif ead_f >= 1_000:
            st.metric("EAD Future", f"TZS {ead_f/1_000:.0f}K")
        else:
            st.metric("EAD Future", f"TZS {ead_f:,.0f}")
    with mcols[3]:
        change = totals.get("total_ead_change", 0)
        delta_color = "inverse" if change > 0 else "normal"
        if abs(change) >= 1_000_000:
            st.metric("EAD Change", f"TZS {change/1_000_000:+.1f}M",
                       delta_color=delta_color)
        else:
            st.metric("EAD Change", f"TZS {change:+,.0f}",
                       delta_color=delta_color)

    # ── Per-district breakdown ──
    if district_risk:
        st.markdown("**District Flood Risk Ranking**")
        for i, dr in enumerate(district_risk):
            ead = dr["ead_future"]
            depth = dr["depth_f_rp100"]

            # Color bar by severity
            if ead > 100_000:
                bar_color = "#FF0000"
            elif ead > 10_000:
                bar_color = "#FFA500"
            elif ead > 0:
                bar_color = "#FFFF00"
            else:
                bar_color = "#E8E8E8"

            ead_text = f"TZS {ead/1_000_000:.2f}M" if ead >= 1_000_000 else f"TZS {ead:,.0f}"
            change_pct = ""
            if dr["ead_baseline"] > 0:
                pct = ((dr["ead_future"] - dr["ead_baseline"]) / dr["ead_baseline"]) * 100
                arrow = "+" if pct > 0 else ""
                change_pct = f" ({arrow}{pct:.0f}%)"

            st.markdown(
                f'<div style="background:linear-gradient(90deg, {bar_color}22 0%, '
                f'transparent 100%);padding:6px 12px;border-left:4px solid {bar_color};'
                f'border-radius:4px;margin:3px 0;font-size:12px;">'
                f'<b>{dr["district"]}</b> — {dr["facility_count"]} facilities — '
                f'EAD: {ead_text}{change_pct} — '
                f'Depth RP100: {depth:.2f}m'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Top-risk facilities ──
    with st.expander("Top Risk Facilities", expanded=False):
        top_facilities = get_flood_risk_facilities(tuple(sorted(districts)), limit=20)
        if top_facilities:
            for f in top_facilities:
                ead_text = (f"TZS {f['ead_future']/1_000_000:.2f}M"
                            if f["ead_future"] >= 1_000_000
                            else f"TZS {f['ead_future']:,.0f}")
                st.markdown(
                    f"- **{f['name']}** ({f['district']}) — "
                    f"EAD: {ead_text}, Depth: {f['depth_f_rp100']:.2f}m"
                )
        else:
            st.caption("No facility-level risk data available.")


def render_spatial_analysis_panel(districts: list[str],
                                  key_prefix: str = "spatial"):
    """Render spatial analysis panel — climate exposure per district.

    Shows exposure to temperature, flood, drought, landslide indicators
    exactly as TCVMP displays them.
    """
    if not districts:
        st.caption("No districts selected.")
        return

    with st.spinner("Querying TCVMP spatial analysis data..."):
        exposure = get_spatial_exposure_summary(tuple(sorted(districts)))

    if not exposure:
        st.caption("No spatial analysis data available for these districts.")
        return

    # Group by indicator
    by_indicator = {}
    for row in exposure:
        key = (row["indicator"], row["category"], row["scenario"])
        by_indicator.setdefault(key, []).append(row)

    _cat_icon = {
        "temperature": "🌡",
        "precipitation": "🌧",
        "drought": "☀",
        "composite": "⚠",
        "wind": "💨",
    }
    _cat_color = {
        "temperature": "#E53935",
        "precipitation": "#1E88E5",
        "drought": "#FF8F00",
        "composite": "#6A1B9A",
        "wind": "#00897B",
    }

    for (indicator, category, scenario), rows in by_indicator.items():
        icon = _cat_icon.get(category, "📊")
        color = _cat_color.get(category, "#666")
        total_features = sum(r["feature_count"] for r in rows)
        total_exposed = sum(r["exposed_count"] for r in rows)
        exposure_pct = (total_exposed / total_features * 100) if total_features > 0 else 0

        # Average mean value across districts
        mean_values = [r["value_mean"] for r in rows if r["value_mean"]]
        avg_mean = sum(mean_values) / len(mean_values) if mean_values else 0

        st.markdown(
            f'<div style="background:{color}11;padding:8px 14px;'
            f'border-left:4px solid {color};border-radius:4px;margin:6px 0;">'
            f'<b>{icon} {indicator}</b> '
            f'<span style="font-size:11px;color:#666;">({scenario})</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        cols = st.columns(4)
        with cols[0]:
            st.metric("Facilities", f"{total_features:,}")
        with cols[1]:
            st.metric("Exposed", f"{total_exposed:,}")
        with cols[2]:
            st.metric("Exposure %", f"{exposure_pct:.1f}%")
        with cols[3]:
            st.metric("Mean Value", f"{avg_mean:.2f}")

        # Per-district detail (collapsed)
        if len(rows) > 1:
            with st.expander(f"Districts ({len(rows)})", expanded=False):
                for r in sorted(rows, key=lambda x: -x["exposed_count"]):
                    exp_pct = (r["exposed_count"] / r["feature_count"] * 100
                               if r["feature_count"] > 0 else 0)
                    st.markdown(
                        f"- **{r['district']}**: {r['exposed_count']:,}/{r['feature_count']:,} "
                        f"exposed ({exp_pct:.0f}%) — "
                        f"range [{r['value_min']:.2f}, {r['value_max']:.2f}], "
                        f"mean {r['value_mean']:.2f}"
                    )


def render_tcvmp_analysis(districts_by_tier: dict, key_prefix: str = "tcvmp"):
    """Render the complete TCVMP analysis panel with tabs.

    This is the main entry point that matches the TCVMP system view:
      Tab 1: Infrastructure Exposure (facility counts by tier)
      Tab 2: Flood Risk Assessment (EAD, depth, damage)
      Tab 3: Climate Exposure (spatial analysis indicators)
    """
    all_districts = []
    for dists in districts_by_tier.values():
        all_districts.extend(dists)

    if not all_districts:
        st.caption("No districts flagged — TCVMP analysis requires district selection.")
        return

    if not is_tcvmp_available():
        st.warning(
            "TCVMP database not available. Check that the TCVMP system "
            "and PostGIS are running."
        )
        return

    tabs = st.tabs([
        "Infrastructure Exposure",
        "Flood Risk Assessment",
        "Climate Exposure Analysis",
    ])

    with tabs[0]:
        render_exposure_analysis(districts_by_tier, key_prefix=f"{key_prefix}_exp")

    with tabs[1]:
        render_flood_risk_panel(all_districts, key_prefix=f"{key_prefix}_risk")

    with tabs[2]:
        render_spatial_analysis_panel(all_districts, key_prefix=f"{key_prefix}_spa")
