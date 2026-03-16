"""Tests for data models."""

import sys
sys.path.insert(0, "/home/kaijage/model/EW")

from datetime import date, time
import pytest

from src.models.common import (
    AlertLevel, LikelihoodLevel, ImpactLevel,
    HazardType, Language, RatingPair, MapImage
)
from src.models.seven22e4 import HazardEntry, FiveDayEntry, Seven22E4Bulletin
from src.models.multirisk import (
    MultiriskBulletin, MultiriskDayForecast, DaySummary,
    AlertTierEntry, TmaComment, MowComment, DmdComment
)


# --- Enum Tests ---

def test_alert_levels():
    assert AlertLevel.NO_WARNING.value == "NO_WARNING"
    assert AlertLevel.ADVISORY.value == "ADVISORY"
    assert AlertLevel.WARNING.value == "WARNING"
    assert AlertLevel.MAJOR_WARNING.value == "MAJOR_WARNING"


def test_hazard_types():
    assert HazardType.HEAVY_RAIN.value == "HEAVY_RAIN"
    assert HazardType.STRONG_WIND.value == "STRONG_WIND"
    assert HazardType.LARGE_WAVES.value == "LARGE_WAVES"
    assert HazardType.FLOODS.value == "FLOODS"


def test_likelihood_impact_levels():
    for level in ["LOW", "MEDIUM", "HIGH"]:
        assert LikelihoodLevel(level).value == level
        assert ImpactLevel(level).value == level


def test_languages():
    assert Language.EN.value == "en"
    assert Language.SW.value == "sw"


# --- RatingPair Tests ---

def test_rating_pair():
    r = RatingPair(LikelihoodLevel.MEDIUM, ImpactLevel.MEDIUM)
    assert r.likelihood == LikelihoodLevel.MEDIUM
    assert r.impact == ImpactLevel.MEDIUM


# --- 722E_4 Model Tests ---

def test_hazard_entry():
    h = HazardEntry(
        hazard_type=HazardType.HEAVY_RAIN,
        alert_level=AlertLevel.ADVISORY,
        description="of heavy rain over Kagera",
        rating=RatingPair(LikelihoodLevel.MEDIUM, ImpactLevel.MEDIUM),
        impacts_expected="Localized floods."
    )
    assert h.hazard_type == HazardType.HEAVY_RAIN
    assert h.alert_level == AlertLevel.ADVISORY


def test_five_day_entry_no_warning():
    day = FiveDayEntry(forecast_date=date(2025, 3, 8))
    assert day.is_no_warning is True
    assert day.max_alert_level == AlertLevel.NO_WARNING


def test_five_day_entry_max_alert():
    day = FiveDayEntry(
        forecast_date=date(2025, 3, 10),
        hazards=[
            HazardEntry(HazardType.HEAVY_RAIN, AlertLevel.ADVISORY, "rain"),
            HazardEntry(HazardType.STRONG_WIND, AlertLevel.WARNING, "wind"),
        ]
    )
    assert day.max_alert_level == AlertLevel.WARNING
    assert day.is_no_warning is False


def test_722e4_bulletin_valid():
    days = [
        FiveDayEntry(forecast_date=date(2025, 3, 8 + i))
        for i in range(5)
    ]
    bulletin = Seven22E4Bulletin(
        issue_date=date(2025, 3, 8),
        issue_time=time(15, 30),
        days=days
    )
    assert len(bulletin.days) == 5


def test_722e4_bulletin_invalid_day_count():
    days = [FiveDayEntry(forecast_date=date(2025, 3, 8 + i)) for i in range(4)]
    with pytest.raises(ValueError, match="exactly 5"):
        Seven22E4Bulletin(
            issue_date=date(2025, 3, 8),
            issue_time=time(15, 30),
            days=days
        )


# --- Multirisk Model Tests ---

def test_multirisk_bulletin_valid():
    days = [
        MultiriskDayForecast(
            forecast_date=date(2025, 5, 7 + i),
            day_number=i + 1
        )
        for i in range(3)
    ]
    bulletin = MultiriskBulletin(
        bulletin_number=122,
        issue_date=date(2025, 5, 7),
        issue_time=time(9, 42),
        language=Language.SW,
        days=days
    )
    assert len(bulletin.days) == 3
    assert bulletin.language == Language.SW


def test_multirisk_bulletin_invalid_day_count():
    days = [
        MultiriskDayForecast(forecast_date=date(2025, 5, 7), day_number=1),
        MultiriskDayForecast(forecast_date=date(2025, 5, 8), day_number=2),
    ]
    with pytest.raises(ValueError, match="exactly 3"):
        MultiriskBulletin(
            bulletin_number=122,
            issue_date=date(2025, 5, 7),
            issue_time=time(9, 42),
            language=Language.SW,
            days=days
        )


def test_day_summary():
    s = DaySummary(
        day_number=1,
        major_warning_districts=[],
        warning_districts=[],
        advisory_districts=["Arusha", "Bagamoyo", "Bariadi"]
    )
    assert len(s.advisory_districts) == 3
    assert s.major_warning_districts == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
