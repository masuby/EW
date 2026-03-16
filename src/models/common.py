"""Shared enums and base dataclasses for the bulletin generation system."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AlertLevel(Enum):
    """Alert severity tier."""
    NO_WARNING = "NO_WARNING"
    ADVISORY = "ADVISORY"       # Yellow — EN: ADVISORY, SW: ANGALIZO
    WARNING = "WARNING"         # Orange — EN: WARNING, SW: TAHADHARI
    MAJOR_WARNING = "MAJOR_WARNING"  # Red — EN: MAJOR WARNING, SW: TAHADHARI KUBWA


class LikelihoodLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ImpactLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class HazardType(Enum):
    HEAVY_RAIN = "HEAVY_RAIN"
    STRONG_WIND = "STRONG_WIND"
    LARGE_WAVES = "LARGE_WAVES"
    FLOODS = "FLOODS"
    LANDSLIDES = "LANDSLIDES"
    EXTREME_TEMPERATURE = "EXTREME_TEMPERATURE"


class Language(Enum):
    EN = "en"
    SW = "sw"


@dataclass
class RatingPair:
    """Likelihood + Impact rating used by all agencies."""
    likelihood: LikelihoodLevel
    impact: ImpactLevel


@dataclass
class MapImage:
    """Reference to a map image file."""
    file_path: Optional[str] = None  # Path to PNG/JPG, None = use placeholder
