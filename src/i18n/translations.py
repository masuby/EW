"""Complete English/Swahili translation dictionary for bulletin generation."""

TRANSLATIONS = {
    "en": {
        # --- 722E_4 Headers ---
        "country_name": "UNITED REPUBLIC OF TANZANIA",
        "ministry": "MINISTRY OF TRANSPORT",
        "tma_name": "TANZANIA METEOROLOGICAL AUTHORITY",
        "five_day_title": "Five days Severe weather impact-based forecasts",
        "issued_on": "Issued on {day_name}: {date}: {time} (EAT)",

        # --- Alert Level Labels ---
        "no_warning": "NO WARNING.",
        "advisory": "ADVISORY",
        "warning": "WARNING",
        "major_warning": "MAJOR WARNING",

        # --- Likelihood / Impact ---
        "likelihood": "Likelihood",
        "impact": "Impact",
        "level_low": "LOW",
        "level_medium": "MEDIUM",
        "level_high": "HIGH",

        # --- 722E_4 Content ---
        "impacts_expected": "Impacts expected:",
        "please_be_prepared": "Please be prepared.",
        "key_label": "KEY:",
        "heavy_rain_key": "Heavy rain",
        "strong_wind_key": "Strong wind",
        "large_waves_key": "Large Waves",

        # --- 722E_4 Footer ---
        "correspondence": "All correspondences should be directed to:",
        "director_general": "Director General, Tanzania Meteorological Authority,",
        "address_line1": "University of Dodoma, Administration block, College of Informatics and Virtual Education,",
        "address_line2": "1 CIVE Street, P.O. Box 27, 41218 Dodoma; Tel: + 255 26 2962610: Fax: +255 26 2962610",
        "email_line": "Email: met@meteo.go.tz; Website: www.meteo.go.tz",
        "iso_cert": "(ISO 9001:2015 Certified in Aviation Services)",
        "form_number": "722E-4 _ 04/2023",

        # --- Multirisk Headers ---
        "mr_country": "THE UNITED REPUBLIC OF TANZANIA",
        "mr_subtitle": "Three days impact-based forecast bulletin",
        "mr_issued": "No. {number} Issued on {date}",
        "mr_right_header_new": [
            "THE PRIME MINISTER'S OFFICE",
            "(POLICY, PARLIAMENT AFFAIRS AND COORDINATION)",
            "DISASTER MANAGEMENT DEPARTMENT",
            "EMERGENCY OPERATION",
            "AND COMMUNICATION CENTER",
        ],
        "mr_right_header_old": [
            "DISASTER MANAGEMENT DEPARTMENT",
            "PRIME MINISTER OFFICE",
            "(POLICY, PARLIAMENT AND COORDINATION)",
            "DEPARTMENT OF WATER RESOURCES",
            "MINISTRY OF WATER",
            "TANZANIA METEOROLOGICAL AUTHORITY",
            "MINISTRY OF TRANSPORT",
        ],

        # --- Multirisk Day/Section Headings ---
        "day_heading": "DAY {n} - {date}",
        "hazard_heavy_rain": "Heavy Rain",
        "hazard_large_waves": "Large Waves",
        "hazard_strong_winds": "Strong Winds",
        "hazard_floods": "Floods",
        "hazard_landslides": "Landslides",
        "hazard_extreme_temperature": "Extreme Temperature",
        "multi_hazard_title": "Multi-hazard assessment and recommendations",
        "outlook_heading": "Outlook DAY {n} - {date}",

        # --- Multirisk Comments ---
        "comments_tma": "Comments TMA",
        "comments_mow": "MoW Comments",
        "comments_dmd": "DMD Comments",
        "impacts_possible": "Impacts expected:",
        "no_warning_text": "NO WARNING.",

        # --- Multirisk Summary ---
        "summary_heading": "SUMMARY WARNING DAY {n}",

        # --- Multirisk Footer ---
        "contact_line": "Contact us: eocctz@pmo.go.tz",
        "attribution": (
            "This bulletin for the United Republic of Tanzania is produced by the "
            "Disaster Management Department of the Prime Minister Office with the "
            "technical and scientific assistance of the Tanzania Meteorological "
            "Authority, the Ministry of Water, UNDRR and CIMA Foundation, with "
            "support of the Italian Government."
        ),

        # --- Alert tier labels ---
        "tier_none": "None",
    },

    "sw": {
        # --- General ---
        "country_name": "JAMHURI YA MUUNGANO WA TANZANIA",

        # --- Alert Level Labels ---
        "no_warning": "HAKUNA TAHADHARI.",
        "advisory": "ANGALIZO",
        "warning": "TAHADHARI",
        "major_warning": "TAHADHARI KUBWA",

        # --- Likelihood / Impact ---
        "likelihood": "UWEZEKANO WA KUTOKEA",
        "impact": "KIWANGO CHA ATHARI ZINAZOWEZA KUTOKEA",
        "level_low": "CHINI",
        "level_medium": "WASTANI",
        "level_high": "JUU",

        # --- Multirisk Headers ---
        "mr_subtitle": "Tahadhari ya Hali mbaya ya Hewa na Hatua za Kuchukua",
        "mr_issued": "Toleo Na. {number} Limetolewa tarehe {date} saa {time} mchana",
        "mr_right_header": [
            "OFISI YA WAZIRI MKUU",
            "(SERA, BUNGE NA URATIBU)",
            "IDARA YA MENEJIMENTI YA MAAFA",
            "KITUO CHA OPERESHENI",
            "NA MAWASILIANO YA DHARURA",
        ],

        # --- Multirisk Day/Section Headings ---
        "day_heading": "SIKU YA {n}, tarehe {date}",
        "hazard_heavy_rain": "Mvua Kubwa",
        "hazard_large_waves": "Mawimbi Makubwa",
        "hazard_strong_winds": "Upepo Mkali",
        "hazard_floods": "Mafuriko",
        "hazard_landslides": "Maporomoko ya Ardhi",
        "hazard_extreme_temperature": "Joto/Baridi Kali",
        "multi_hazard_title": "Tathimini ya Kiwango cha Madhara yanayoweza kutokea na Hatua za Kuchukua",
        "outlook_heading": "Uchambuzi wa Majanga na Madhara yanayotarajiwa siku ya {n} tarehe {date}",

        # --- Multirisk Comments ---
        "comments_tma": "Uchambuzi wa kitaalam kutoka Mamlaka ya Hali ya Hewa Tanzania",
        "comments_mow": "Uchambuzi wa kitaalam kutoka Wizara ya Maji",
        "comments_dmd": "Uchambuzi wa kitaalam kutoka Idara ya Menejimenti ya Maafa",
        "impacts_possible": "Madhara yanayoweza kutokea:",
        "no_warning_text": "HAKUNA TAHADHARI.",

        # --- Multirisk Summary ---
        "summary_heading": "Muhtasari wa Maeneo na kiwango cha madhara yanayotarajiwa siku ya {n}",

        # --- Multirisk Footer ---
        "contact_line": "Wasiliana nasi: 190 au eocctz@pmo.go.tz",
        "attribution": (
            "Tahadhari ya Hali mbaya na Hatua za Kuchukua kwa kipindi cha siku tatu "
            "imetolewa na Kituo cha Operesheni na Mawasiliano ya Dharura, Idara ya "
            "Menejimenti ya Maafa, Ofisi ya Waziri Mkuu kwa kushirikiana na Mamlaka "
            "ya Hali ya Hewa Tanzania na Wizara ya Maji"
        ),

        # --- Alert tier labels ---
        "tier_none": "Hakuna",
    },
}


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated string, with optional format parameters."""
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key)
    if text is None:
        # Fallback to English
        text = TRANSLATIONS["en"].get(key, f"[MISSING: {key}]")
    if kwargs and isinstance(text, str):
        return text.format(**kwargs)
    return text


def t_list(key: str, lang: str = "en") -> list[str]:
    """Get translated list (e.g., header lines)."""
    result = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key)
    if result is None:
        result = TRANSLATIONS["en"].get(key, [])
    if isinstance(result, list):
        return result
    return [result]
