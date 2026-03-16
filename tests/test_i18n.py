"""Tests for i18n translations."""

import sys
sys.path.insert(0, "/home/kaijage/model/EW")

import pytest
from src.i18n.translations import TRANSLATIONS, t, t_list


def test_both_languages_exist():
    assert "en" in TRANSLATIONS
    assert "sw" in TRANSLATIONS


def test_critical_keys_exist_in_both():
    """Ensure critical keys exist in both languages."""
    critical_keys = [
        "country_name", "no_warning", "advisory", "warning", "major_warning",
        "likelihood", "impact", "level_low", "level_medium", "level_high",
        "day_heading", "hazard_heavy_rain", "hazard_large_waves",
        "hazard_strong_winds", "hazard_floods", "multi_hazard_title",
        "outlook_heading", "comments_tma", "comments_mow", "comments_dmd",
        "summary_heading", "contact_line", "attribution", "tier_none",
    ]
    for key in critical_keys:
        assert key in TRANSLATIONS["en"], f"Missing EN key: {key}"
        assert key in TRANSLATIONS["sw"], f"Missing SW key: {key}"


def test_t_function_english():
    assert t("advisory", "en") == "ADVISORY"
    assert t("advisory", "sw") == "ANGALIZO"


def test_t_function_with_params():
    result = t("day_heading", "en", n=1, date="08-03-2025")
    assert result == "DAY 1 - 08-03-2025"

    result = t("day_heading", "sw", n=2, date="08-05-2025")
    assert result == "SIKU YA 2, tarehe 08-05-2025"


def test_t_function_fallback():
    # Key only in English should fallback
    result = t("five_day_title", "sw")
    assert result == "Five days Severe weather impact-based forecasts"


def test_t_function_missing_key():
    result = t("nonexistent_key", "en")
    assert "[MISSING:" in result


def test_t_list_function():
    lines = t_list("mr_right_header_new", "en")
    assert isinstance(lines, list)
    assert len(lines) == 5
    assert lines[0] == "THE PRIME MINISTER'S OFFICE"

    sw_lines = t_list("mr_right_header", "sw")
    assert isinstance(sw_lines, list)
    assert len(sw_lines) == 5
    assert sw_lines[0] == "OFISI YA WAZIRI MKUU"


def test_alert_level_translations():
    """Verify the exact English → Swahili alert mappings."""
    assert t("major_warning", "en") == "MAJOR WARNING"
    assert t("major_warning", "sw") == "TAHADHARI KUBWA"
    assert t("warning", "en") == "WARNING"
    assert t("warning", "sw") == "TAHADHARI"
    assert t("advisory", "en") == "ADVISORY"
    assert t("advisory", "sw") == "ANGALIZO"
    assert t("no_warning", "en") == "NO WARNING."
    assert t("no_warning", "sw") == "HAKUNA TAHADHARI."


def test_likelihood_impact_translations():
    assert t("level_medium", "en") == "MEDIUM"
    assert t("level_medium", "sw") == "WASTANI"
    assert t("level_low", "sw") == "CHINI"
    assert t("level_high", "sw") == "JUU"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
