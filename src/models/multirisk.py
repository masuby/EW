"""Data models for the Tanzania Multirisk Three Days Impact-Based Forecast Bulletin."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional

from .common import (
    AlertLevel, HazardType, Language, RatingPair, MapImage
)


@dataclass
class HazardMapPanel:
    """A single hazard type map panel for a given day."""
    hazard_type: HazardType
    map_image: Optional[MapImage] = None


@dataclass
class AlertTierEntry:
    """Content for a single alert tier in the multi-hazard assessment."""
    alert_level: AlertLevel
    text: Optional[str] = None  # Text next to label (e.g., "None" / "Hakuna")
    recommendations: list[str] = field(default_factory=list)


@dataclass
class AlertCommentEntry:
    """A single alert paragraph within an agency comment."""
    alert_level: AlertLevel
    description: str
    rating: Optional[RatingPair] = None


@dataclass
class TmaComment:
    """TMA expert analysis."""
    entries: list[AlertCommentEntry] = field(default_factory=list)


@dataclass
class MowComment:
    """Ministry of Water expert analysis."""
    entries: list[AlertCommentEntry] = field(default_factory=list)


@dataclass
class DmdComment:
    """DMD impact assessment with bullet points."""
    header_text: Optional[str] = None  # e.g., "Madhara yanayoweza kutokea:"
    impact_bullets: list[str] = field(default_factory=list)
    rating: Optional[RatingPair] = None


@dataclass
class MultiriskDayForecast:
    """Complete forecast data for a single day."""
    forecast_date: date
    day_number: int  # 1, 2, or 3

    # Page A: Maps
    hazard_panels: list[HazardMapPanel] = field(default_factory=list)
    summary_map: Optional[MapImage] = None
    alert_tiers: list[AlertTierEntry] = field(default_factory=list)

    # Recommendation section
    recommendation_intro: Optional[str] = None
    recommendations: list[str] = field(default_factory=list)
    committee_note: Optional[str] = None

    # Page B: Comments
    tma_comment: Optional[TmaComment] = None
    mow_comment: Optional[MowComment] = None
    dmd_comment: Optional[DmdComment] = None


@dataclass
class DaySummary:
    """District summary for a single day on the summary page."""
    day_number: int
    major_warning_districts: list[str] = field(default_factory=list)
    warning_districts: list[str] = field(default_factory=list)
    advisory_districts: list[str] = field(default_factory=list)


@dataclass
class MultiriskBulletin:
    """Complete Multirisk Three Days Impact-Based Forecast bulletin."""
    bulletin_number: int
    issue_date: date
    issue_time: time
    language: Language

    days: list[MultiriskDayForecast]  # Exactly 3 entries
    day_summaries: list[DaySummary] = field(default_factory=list)

    # Header variant: "new" = PMO/EOCC (from #079 onward), "old" = DMD/DWR/TMA
    header_variant: str = "new"

    def __post_init__(self):
        if len(self.days) != 3:
            raise ValueError(
                f"Multirisk bulletin must have exactly 3 day entries, got {len(self.days)}"
            )
