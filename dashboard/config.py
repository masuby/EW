"""Dashboard configuration — dynamic geodata, colors, paths."""

import json
from pathlib import Path

import geopandas as gpd
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
GEODATA_DIR = ASSETS_DIR / "geodata"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
DOCUMENTS_DIR = PROJECT_ROOT / "documents"
OUTPUT_DIR = PROJECT_ROOT / "output"
TMA_OUTPUT_DIR = OUTPUT_DIR / "tma"
DMD_OUTPUT_DIR = OUTPUT_DIR / "dmd"
MOW_OUTPUT_DIR = OUTPUT_DIR / "mow"
GST_OUTPUT_DIR = OUTPUT_DIR / "gst"
MOH_OUTPUT_DIR = OUTPUT_DIR / "moh"
MOA_OUTPUT_DIR = OUTPUT_DIR / "moa"
NEMC_OUTPUT_DIR = OUTPUT_DIR / "nemc"

# Ensure output dirs
for _d in [TMA_OUTPUT_DIR, DMD_OUTPUT_DIR, MOW_OUTPUT_DIR,
           GST_OUTPUT_DIR, MOH_OUTPUT_DIR, MOA_OUTPUT_DIR, NEMC_OUTPUT_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# Default alert level colors (user can customize via color pickers)
DEFAULT_COLORS = {
    "advisory": "#FFFF00",       # Yellow
    "warning": "#FFA500",        # Orange
    "major_warning": "#FF0000",  # Red
    "no_data": "#E8E8E8",        # Light gray
    "selected": "#90CAF9",       # Light blue (for generic selection)
}

# Alert level display config
ALERT_LEVELS = [
    {"key": "NO_WARNING", "label": "No Warning", "label_sw": "Hakuna Onyo", "color": "#E8E8E8"},
    {"key": "ADVISORY", "label": "Advisory", "label_sw": "Angalizo", "color": "#FFFF00"},
    {"key": "WARNING", "label": "Warning", "label_sw": "Tahadhari", "color": "#FFA500"},
    {"key": "MAJOR_WARNING", "label": "Major Warning", "label_sw": "Tahadhari Kubwa", "color": "#FF0000"},
]

HAZARD_TYPES = [
    {"key": "HEAVY_RAIN", "label": "Heavy Rain", "label_sw": "Mvua Kubwa", "icon": "cloud-rain", "icon_file": "heavy_rain.png"},
    {"key": "LARGE_WAVES", "label": "Large Waves", "label_sw": "Mawimbi Makubwa", "icon": "water", "icon_file": "large_waves.png"},
    {"key": "STRONG_WIND", "label": "Strong Wind", "label_sw": "Upepo Mkali", "icon": "wind", "icon_file": "strong_wind.png"},
    {"key": "FLOODS", "label": "Floods", "label_sw": "Mafuriko", "icon": "house-flood-water", "icon_file": "floods.png"},
    {"key": "LANDSLIDES", "label": "Landslides", "label_sw": "Maporomoko ya Ardhi", "icon": "mountain", "icon_file": "landslides.png"},
    {"key": "EXTREME_TEMPERATURE", "label": "Extreme Temperature", "label_sw": "Joto/Baridi Kali", "icon": "temperature-high", "icon_file": "extreme_temperature.png"},
]

# --- Agency-specific hazard types ---

# GST — Geological Survey of Tanzania
GST_HAZARD_TYPES = [
    {"key": "EARTHQUAKE", "label": "Earthquake", "label_sw": "Tetemeko la Ardhi", "icon": "globe", "icon_file": "earthquake.png"},
    {"key": "LANDSLIDES", "label": "Landslide", "label_sw": "Maporomoko ya Ardhi", "icon": "mountain", "icon_file": "landslides.png"},
    {"key": "VOLCANO", "label": "Volcano", "label_sw": "Volkano", "icon": "fire", "icon_file": "volcano.png"},
]

# MoH — Ministry of Health
MOH_HAZARD_TYPES = [
    {"key": "DISEASE_OUTBREAK", "label": "Disease Outbreak", "label_sw": "Mlipuko wa Magonjwa", "icon": "biohazard", "icon_file": "disease_outbreak.png"},
]

# MoA — Ministry of Agriculture
MOA_HAZARD_TYPES = [
    {"key": "DROUGHT", "label": "Drought", "label_sw": "Ukame", "icon": "sun", "icon_file": "drought.png"},
]

# NEMC — National Environment Management Council
NEMC_HAZARD_TYPES = [
    {"key": "AIR_POLLUTION", "label": "Air Pollution", "label_sw": "Uchafuzi wa Hewa", "icon": "smog", "icon_file": "air_pollution.png"},
]

# GST severity levels (earthquake-specific)
GST_SEVERITY_LEVELS = [
    {"key": "MINOR", "label": "Minor (< 3.0)", "color": "#90EE90"},
    {"key": "LIGHT", "label": "Light (3.0-3.9)", "color": "#FFFF00"},
    {"key": "MODERATE", "label": "Moderate (4.0-4.9)", "color": "#FFA500"},
    {"key": "STRONG", "label": "Strong (5.0-5.9)", "color": "#FF4500"},
    {"key": "MAJOR", "label": "Major (6.0+)", "color": "#FF0000"},
]

# Default impacts per new hazard type
DEFAULT_IMPACTS_NEW = {
    "EARTHQUAKE": {
        "en": "Structural damage to buildings and infrastructure. Risk of aftershocks.",
        "sw": "Uharibifu wa majengo na miundombinu. Hatari ya mitetemeko ya ziada.",
    },
    "VOLCANO": {
        "en": "Ash fall, lava flows, and toxic gas emissions affecting nearby communities.",
        "sw": "Majivu, mtiririko wa lava, na uzalishaji wa gesi sumu unaoathiri jamii jirani.",
    },
    "DISEASE_OUTBREAK": {
        "en": "Rapid spread of infectious disease requiring immediate public health response.",
        "sw": "Kuenea kwa kasi kwa magonjwa ya kuambukiza kunakohitaji hatua za haraka za afya ya umma.",
    },
    "DROUGHT": {
        "en": "Crop failure, water scarcity, and livestock mortality affecting food security.",
        "sw": "Kushindwa kwa mazao, uhaba wa maji, na vifo vya mifugo kunakoathiri usalama wa chakula.",
    },
    "AIR_POLLUTION": {
        "en": "Hazardous air quality levels posing respiratory health risks.",
        "sw": "Viwango hatari vya ubora wa hewa vinavyosababisha hatari za afya ya kupumua.",
    },
}

LIKELIHOOD_LEVELS = ["LOW", "MEDIUM", "HIGH"]
IMPACT_LEVELS = ["LOW", "MEDIUM", "HIGH"]

# Map styling matching the pipeline (src/builders/map_generator.py)
MAP_COLORS = {
    "advisory": "#FFFF00",
    "warning": "#FFA500",
    "major_warning": "#FF0000",
    "no_data": "#FFFFFF",
    "boundary": "#999999",
    "region_boundary": "#000000",
    "country_border": "#222222",
    "water": "#B0D4F1",
    "background": "#FFFFFF",
}

# Manual label position adjustments for crowded/island regions
REGION_LABEL_ADJUSTMENTS = {
    "Dar es Salaam": (0.3, -0.15),
    "Kaskazini Unguja": (0.5, 0.1),
    "Kusini Unguja": (0.5, -0.1),
    "Kaskazini Pemba": (0.5, 0.1),
    "Kusini Pemba": (0.5, -0.1),
    "Mjini Magharibi": (0.6, 0.0),
}

# Tanzania bounding box (lon_min, lat_min, lon_max, lat_max)
TZ_BOUNDS = (28, -12, 41, 1)


@st.cache_data
def load_regions_geodata() -> dict:
    """Load Tanzania region boundaries as GeoJSON dict."""
    path = GEODATA_DIR / "gadm41_TZA_1.json.zip"
    gdf = gpd.read_file(f"zip://{path}")
    # Add clean display names
    gdf["display_name"] = gdf["NAME_1"].apply(_clean_region_name)
    return json.loads(gdf.to_json())


@st.cache_data
def load_districts_geodata() -> dict:
    """Load Tanzania district boundaries as GeoJSON dict."""
    path = GEODATA_DIR / "gadm41_TZA_2.json.zip"
    gdf = gpd.read_file(f"zip://{path}")
    gdf["display_name"] = gdf["NAME_2"].apply(_clean_district_name)
    gdf["region"] = gdf["NAME_1"].apply(_clean_region_name)
    return json.loads(gdf.to_json())


@st.cache_data
def get_region_names() -> list[str]:
    """Get sorted list of region display names."""
    geojson = load_regions_geodata()
    names = [f["properties"]["display_name"] for f in geojson["features"]]
    return sorted(set(names))


@st.cache_data
def get_district_names() -> list[str]:
    """Get sorted list of district display names."""
    geojson = load_districts_geodata()
    names = [f["properties"]["display_name"] for f in geojson["features"]]
    return sorted(set(names))


@st.cache_data
def get_districts_by_region() -> dict[str, list[str]]:
    """Get districts grouped by region."""
    geojson = load_districts_geodata()
    by_region = {}
    for f in geojson["features"]:
        region = f["properties"]["region"]
        district = f["properties"]["display_name"]
        by_region.setdefault(region, []).append(district)
    for k in by_region:
        by_region[k] = sorted(by_region[k])
    return by_region


@st.cache_data
def load_lakes_geodata():
    """Load Natural Earth lakes clipped to Tanzania boundary."""
    path = GEODATA_DIR / "ne_10m_lakes.zip"
    if not path.exists():
        return None
    gdf = gpd.read_file(f"zip://{path}")
    nearby = gdf.cx[TZ_BOUNDS[0]:TZ_BOUNDS[2], TZ_BOUNDS[1]:TZ_BOUNDS[3]]
    # Clip to country boundary
    regions = gpd.read_file(f"zip://{GEODATA_DIR / 'gadm41_TZA_1.json.zip'}")
    country = regions.dissolve()
    clipped = gpd.clip(nearby, country)
    return clipped if len(clipped) > 0 else None


@st.cache_data
def load_rivers_geodata():
    """Load Natural Earth rivers clipped to Tanzania boundary."""
    path = GEODATA_DIR / "ne_10m_rivers.zip"
    if not path.exists():
        return None
    gdf = gpd.read_file(f"zip://{path}")
    nearby = gdf.cx[TZ_BOUNDS[0]:TZ_BOUNDS[2], TZ_BOUNDS[1]:TZ_BOUNDS[3]]
    regions = gpd.read_file(f"zip://{GEODATA_DIR / 'gadm41_TZA_1.json.zip'}")
    country = regions.dissolve()
    clipped = gpd.clip(nearby, country)
    return clipped if len(clipped) > 0 else None


@st.cache_data
def load_country_boundary():
    """Load dissolved Tanzania country boundary."""
    path = GEODATA_DIR / "gadm41_TZA_1.json.zip"
    gdf = gpd.read_file(f"zip://{path}")
    return gdf.dissolve()


def _clean_region_name(name: str) -> str:
    """Convert geodata region names to human-readable format."""
    # GADM uses names like 'DaresSalaam', 'KaskaziniPemba'
    mappings = {
        "DaresSalaam": "Dar es Salaam",
        "KaskaziniPemba": "Kaskazini Pemba",
        "KaskaziniUnguja": "Kaskazini Unguja",
        "KusiniPemba": "Kusini Pemba",
        "KusiniUnguja": "Kusini Unguja",
        "MjiniMagharibi": "Mjini Magharibi",
    }
    return mappings.get(name, name)


def _clean_district_name(name: str) -> str:
    """Convert geodata district names to human-readable format."""
    # Insert spaces before capital letters in camelCase names
    import re
    result = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
    return result


# --- Default Template Texts (from reference bulletins) ---

DEFAULT_TEXTS = {
    "sw": {
        "recommendation_intro": (
            "Jamii inasisitizwa kuchukua hatua za tahadhari ikijumuisha:"
        ),
        "recommendations": [
            "Wavuvi na watumiaji wa bahari ya Hindi kuchukua tahadhari ya upepo mkali na mawimbi makubwa.",
            "Kuepuka kuvuka barabara na madaraja yaliyojaa maji.",
            "Watu wanaoishi maeneo ya mabondeni kuchukua tahadhari.",
            "Walimu na wazazi kuchukua tahadhari kwa wanafunzi wanaopita katika maeneo hatarishi.",
            "Makundi maalamu ikijumuisha watu wenye ulemavu, watoto na wazee wapatiwe taarifa ya tahadhari ya mapema na hatua stahiki zichukuliwe na jamii husika.",
            "Kuendelea kufuatilia taarifa za hali ya hewa zinazotolewa na Mamlaka ya Hali ya Hewa Tanzania.",
        ],
        "committee_note": (
            "Kamati za Usimamizi wa Maafa za Mikoa, Wilaya, Kata na Vijiji/Mitaa "
            "zinatakiwa kuchukua hatua stahiki za kujiandaa na kukabiliana na maafa "
            "ili kupunguza athari za majanga."
        ),
        "dmd_header": "Madhara yanayoweza kutokea:",
        "dmd_bullets": [
            "Makazi kuzingirwa na maji.",
            "Uwezekano wa kuathirika kwa shughuli za uvuvi na usafirishaji katika bahari ya Hindi.",
            "Uwezekano wa uharibifu wa miundombinu ya barabara na madaraja.",
            "Uwezekano wa barabara kutopitika kutokana na mafuriko.",
            "Kuathirika kwa shughuli za kijamii na kiuchumi.",
        ],
    },
    "en": {
        "recommendation_intro": (
            "The public is urged to take precautionary measures including:"
        ),
        "recommendations": [
            "Fishers and sea users to take precautions against strong winds and large waves.",
            "Avoid crossing flooded roads and bridges.",
            "People living in low-lying areas to take precautionary measures.",
            "Teachers and parents to take precautions for students passing through hazardous areas.",
            "Special groups including persons with disabilities, children and elderly to be informed of early warning and appropriate measures taken.",
            "Continue monitoring weather information from Tanzania Meteorological Authority.",
        ],
        "committee_note": (
            "Disaster Management Committees at Regional, District, Ward and Village/Street "
            "levels are required to take appropriate measures to prepare for and respond to "
            "disasters in order to reduce the impact of hazards."
        ),
        "dmd_header": "Possible impacts:",
        "dmd_bullets": [
            "Residential areas may be waterlogged.",
            "Possible disruption of fishing and marine transport activities.",
            "Possible damage to road and bridge infrastructure.",
            "Roads may become impassable due to flooding.",
            "Disruption of socio-economic activities.",
        ],
    },
}

# TMA hazard description templates
TMA_DESCRIPTION_TEMPLATES = {
    "HEAVY_RAIN": {
        "en": "of heavy rain is issued over few areas of {regions}.",
        "sw": "la mvua kubwa limetolewa kwa maeneo machache ya mikoa ya {regions}.",
    },
    "STRONG_WIND": {
        "en": "of strong wind reaching {speed} km/h is issued over coastal areas of {regions}.",
        "sw": "la upepo mkali unaofikia kilomita {speed} kwa saa limetolewa kwa {regions}.",
    },
    "LARGE_WAVES": {
        "en": "of large waves reaching {height} meters is issued over coastal areas.",
        "sw": "la mawimbi makubwa yanayofikia mita {height} limetolewa kwa maeneo ya pwani.",
    },
    "FLOODS": {
        "en": "of floods is issued over few areas of {regions}.",
        "sw": "la mafuriko limetolewa kwa maeneo machache ya mikoa ya {regions}.",
    },
    "LANDSLIDES": {
        "en": "of landslides is issued over hilly and mountainous areas of {regions}.",
        "sw": "la maporomoko ya ardhi limetolewa kwa maeneo ya milima ya {regions}.",
    },
    "EXTREME_TEMPERATURE": {
        "en": "of extreme temperature is issued over {regions}.",
        "sw": "la joto/baridi kali limetolewa kwa maeneo ya {regions}.",
    },
}

# Default impacts expected per hazard type
DEFAULT_IMPACTS_EXPECTED = {
    "HEAVY_RAIN": {
        "en": "Localized floods and disruption of socio-economic activities over few areas.",
        "sw": "Mafuriko ya ndani na usumbufu wa shughuli za kijamii na kiuchumi.",
    },
    "STRONG_WIND": {
        "en": "Damage to structures and disruption of outdoor activities.",
        "sw": "Uharibifu wa miundombinu na usumbufu wa shughuli za nje.",
    },
    "LARGE_WAVES": {
        "en": "Disruption of fishing and marine transport activities.",
        "sw": "Usumbufu wa shughuli za uvuvi na usafirishaji wa baharini.",
    },
    "FLOODS": {
        "en": "Damage to infrastructure and displacement of communities.",
        "sw": "Uharibifu wa miundombinu na kuhama kwa jamii.",
    },
    "LANDSLIDES": {
        "en": "Destruction of settlements, roads and farmlands in hilly areas.",
        "sw": "Uharibifu wa makazi, barabara na mashamba katika maeneo ya vilima.",
    },
    "EXTREME_TEMPERATURE": {
        "en": "Heat stress, crop damage and disruption of daily activities.",
        "sw": "Msongo wa joto, uharibifu wa mazao na usumbufu wa shughuli za kila siku.",
    },
}


# --- River Basin / Catchment to District Mapping (for MoW) ---
# Tanzania's major water basins and the districts they affect
CATCHMENT_BASINS = {
    "Pangani": {
        "label": "Pangani Basin",
        "districts": [
            "Hai", "Moshi Rural", "Moshi Urban", "Mwanga", "Rombo", "Same", "Siha",
            "Korogwe", "Korogwe Town", "Lushoto", "Muheza", "Pangani", "Handeni",
            "Handeni Town", "Kilindi", "Mkinga", "Tanga",
            "Babati", "Babati Urban", "Simanjiro",
        ],
    },
    "Wami-Ruvu": {
        "label": "Wami / Ruvu Basin",
        "districts": [
            "Bagamoyo", "Kibaha", "Kibaha Urban", "Kisarawe", "Mkuranga",
            "Morogoro Rural", "Morogoro Urban", "Mvomero", "Gairo",
            "Kilosa", "Chamwino", "Dodoma Urban", "Kongwa", "Mpwapwa",
            "Ilala", "Kinondoni", "Temeke",
        ],
    },
    "Rufiji": {
        "label": "Rufiji Basin",
        "districts": [
            "Rufiji", "Kilombero", "Ulanga", "Mafia",
            "Iringa Rural", "Iringa Urban", "Kilolo", "Mufindi", "Mafinga Town",
            "Ludewa", "Makete", "Njombe Rural", "Njombe Urban",
            "Makambako Town", "Wanging'ombe",
            "Mbarali", "Chunya",
            "Manyoni", "Ikungi",
        ],
    },
    "Ruvuma": {
        "label": "Ruvuma Basin",
        "districts": [
            "Songea Rural", "Songea Urban", "Mbinga", "Nyasa",
            "Namtumbo", "Tunduru",
            "Nachingwea", "Liwale", "Ruangwa",
            "Masasi", "Masasi Town", "Nanyumbu", "Newala", "Tandahimba",
            "Mtwara Rural", "Mtwara Urban",
        ],
    },
    "Lake Victoria": {
        "label": "Lake Victoria Basin",
        "districts": [
            "Ilemela", "Kwimba", "Magu", "Misungwi", "Nyamagana", "Sengerema", "Ukerewe",
            "Bukoba Rural", "Bukoba Urban", "Karagwe", "Kyerwa", "Missenyi", "Muleba", "Ngara",
            "Biharamulo",
            "Bunda", "Butiama", "Musoma Rural", "Musoma Urban", "Rorya", "Serengeti", "Tarime",
            "Geita", "Mbogwe", "Nyang'hwale", "Bukombe", "Chato",
            "Bariadi", "Busega", "Itilima", "Maswa", "Meatu",
            "Kahama", "Kahama Town", "Kishapu", "Shinyanga Rural", "Shinyanga Urban",
        ],
    },
    "Lake Tanganyika": {
        "label": "Lake Tanganyika Basin",
        "districts": [
            "Kigoma Rural", "Kigoma Urban", "Kasulu", "Kasulu Town",
            "Buhigwe", "Kakonko", "Kibondo", "Uvinza",
            "Nkasi", "Sumbawanga Rural", "Sumbawanga Urban", "Kalambo",
            "Mpanda Rural", "Mpanda Urban", "Mlele",
        ],
    },
    "Lake Nyasa": {
        "label": "Lake Nyasa Basin",
        "districts": [
            "Ludewa", "Nyasa", "Mbinga",
            "Kyela", "Rungwe", "Mbeya Rural", "Mbeya Urban",
            "Ileje", "Mbozi", "Momba", "Songwe", "Tunduma",
        ],
    },
    "Lake Rukwa": {
        "label": "Lake Rukwa Basin",
        "districts": [
            "Sumbawanga Rural", "Sumbawanga Urban", "Nkasi", "Kalambo",
            "Mpanda Rural", "Mpanda Urban", "Mlele",
            "Chunya", "Mbarali",
        ],
    },
    "Internal Drainage": {
        "label": "Internal Drainage Basin",
        "districts": [
            "Bahi", "Chamwino", "Chemba", "Dodoma Urban", "Kondoa",
            "Singida Rural", "Singida Urban", "Iramba", "Mkalama",
            "Hanang", "Mbulu", "Karatu",
            "Ngorongoro", "Monduli", "Longido", "Arusha", "Arusha Urban", "Meru",
            "Kiteto", "Simanjiro",
            "Igunga", "Nzega", "Sikonge", "Tabora", "Urambo", "Uyui", "Kaliua",
        ],
    },
    "Indian Ocean Coast": {
        "label": "Indian Ocean Coastal",
        "districts": [
            "Tanga", "Pangani", "Mkinga", "Bagamoyo",
            "Ilala", "Kinondoni", "Temeke",
            "Kibaha", "Mkuranga", "Mafia", "Rufiji",
            "Kilwa", "Lindi Rural", "Lindi Urban",
            "Mtwara Rural", "Mtwara Urban",
        ],
    },
}


def get_catchment_names() -> list[str]:
    """Get sorted list of catchment basin names."""
    return sorted(CATCHMENT_BASINS.keys())


def get_districts_by_catchment() -> dict[str, list[str]]:
    """Get districts grouped by catchment basin."""
    return {k: sorted(v["districts"]) for k, v in CATCHMENT_BASINS.items()}


def get_raw_region_name(display_name: str) -> str:
    """Convert display name back to geodata raw name for pipeline."""
    reverse = {
        "Dar es Salaam": "DaresSalaam",
        "Kaskazini Pemba": "KaskaziniPemba",
        "Kaskazini Unguja": "KaskaziniUnguja",
        "Kusini Pemba": "KusiniPemba",
        "Kusini Unguja": "KusiniUnguja",
        "Mjini Magharibi": "MjiniMagharibi",
    }
    return reverse.get(display_name, display_name)
