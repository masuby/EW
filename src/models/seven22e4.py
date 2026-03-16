"""Data models for the 722E_4 Five Days Severe Weather Impact-Based Forecast."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional

from .common import AlertLevel, HazardType, RatingPair, MapImage


@dataclass
class HazardEntry:
    """A single hazard within a day's forecast."""
    hazard_type: HazardType
    alert_level: AlertLevel
    description: str  # e.g., "of heavy rain is issued over few areas of Ruvuma..."
    rating: Optional[RatingPair] = None  # None when NO_WARNING
    impacts_expected: Optional[str] = None  # e.g., "Localized floods over few areas."
    regions: list[str] = field(default_factory=list)  # For auto-map generation
    drawn_shapes: list[dict] = field(default_factory=list)  # GeoJSON features from draw tool


@dataclass
class FiveDayEntry:
    """Forecast for a single day in the 722E_4 bulletin."""
    forecast_date: date
    hazards: list[HazardEntry] = field(default_factory=list)
    map_image: Optional[MapImage] = None

    @property
    def max_alert_level(self) -> AlertLevel:
        """Return highest alert level across all hazards for this day."""
        priority = {
            AlertLevel.NO_WARNING: 0,
            AlertLevel.ADVISORY: 1,
            AlertLevel.WARNING: 2,
            AlertLevel.MAJOR_WARNING: 3,
        }
        if not self.hazards:
            return AlertLevel.NO_WARNING
        return max(self.hazards, key=lambda h: priority[h.alert_level]).alert_level

    @property
    def is_no_warning(self) -> bool:
        return self.max_alert_level == AlertLevel.NO_WARNING


@dataclass
class Seven22E4Bulletin:
    """Complete 722E_4 Five Days Severe Weather bulletin."""
    issue_date: date
    issue_time: time  # Typically 15:30 EAT
    days: list[FiveDayEntry]  # Exactly 5 entries

    def __post_init__(self):
        if len(self.days) != 5:
            raise ValueError(
                f"722E_4 bulletin must have exactly 5 day entries, got {len(self.days)}"
            )
