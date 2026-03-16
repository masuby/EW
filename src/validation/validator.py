"""Input JSON validation for bulletin data."""

from datetime import date, time
from typing import Any

from ..models.common import AlertLevel, HazardType, LikelihoodLevel, ImpactLevel, Language, RatingPair, MapImage
from ..models.seven22e4 import HazardEntry, FiveDayEntry, Seven22E4Bulletin
from ..models.multirisk import (
    MultiriskBulletin, MultiriskDayForecast, DaySummary,
    AlertTierEntry, TmaComment, MowComment, DmdComment,
    AlertCommentEntry, HazardMapPanel,
)


def _parse_date(s: str) -> date:
    """Parse date from various formats."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}")


def _parse_time(s: str) -> time:
    """Parse time from string."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time: {s}")


def _parse_rating(data: dict) -> RatingPair | None:
    """Parse a likelihood/impact rating pair from dict."""
    if not data:
        return None
    likelihood = data.get("likelihood")
    impact = data.get("impact")
    if not likelihood or not impact:
        return None
    return RatingPair(
        likelihood=LikelihoodLevel(likelihood),
        impact=ImpactLevel(impact),
    )


def validate_and_parse_722e4(data: dict) -> Seven22E4Bulletin:
    """Validate and parse 722E_4 input JSON into a Seven22E4Bulletin."""
    errors = []

    if "issue_date" not in data:
        errors.append("Missing required field: issue_date")
    if "issue_time" not in data:
        errors.append("Missing required field: issue_time")
    if "days" not in data:
        errors.append("Missing required field: days")
    elif len(data["days"]) != 5:
        errors.append(f"722E_4 requires exactly 5 days, got {len(data['days'])}")

    if errors:
        raise ValueError("Validation errors:\n" + "\n".join(f"  - {e}" for e in errors))

    issue_date = _parse_date(data["issue_date"])
    issue_time = _parse_time(data["issue_time"])

    days = []
    for i, day_data in enumerate(data["days"]):
        forecast_date = _parse_date(day_data["date"])

        hazards = []
        for h_data in day_data.get("hazards", []):
            hazards.append(HazardEntry(
                hazard_type=HazardType(h_data["type"]),
                alert_level=AlertLevel(h_data["alert_level"]),
                description=h_data.get("description", ""),
                rating=_parse_rating(h_data) if h_data.get("likelihood") else None,
                impacts_expected=h_data.get("impacts_expected"),
                regions=h_data.get("regions", []),
                drawn_shapes=h_data.get("drawn_shapes", []),
            ))

        map_img = None
        if day_data.get("map_image"):
            map_img = MapImage(file_path=day_data["map_image"])

        days.append(FiveDayEntry(
            forecast_date=forecast_date,
            hazards=hazards,
            map_image=map_img,
        ))

    return Seven22E4Bulletin(
        issue_date=issue_date,
        issue_time=issue_time,
        days=days,
    )


def validate_and_parse_multirisk(data: dict) -> MultiriskBulletin:
    """Validate and parse Multirisk input JSON into a MultiriskBulletin."""
    errors = []

    for field in ["bulletin_number", "issue_date", "issue_time", "language", "days"]:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "days" in data and len(data["days"]) != 3:
        errors.append(f"Multirisk requires exactly 3 days, got {len(data['days'])}")

    if errors:
        raise ValueError("Validation errors:\n" + "\n".join(f"  - {e}" for e in errors))

    issue_date = _parse_date(data["issue_date"])
    issue_time = _parse_time(data["issue_time"])
    language = Language(data["language"])

    days = []
    for day_data in data["days"]:
        forecast_date = _parse_date(day_data["date"])
        day_number = day_data["day_number"]

        # Parse hazard panels
        hazard_panels = []
        for hp_data in day_data.get("hazard_panels", []):
            hazard_panels.append(HazardMapPanel(
                hazard_type=HazardType(hp_data["type"]),
                map_image=MapImage(hp_data["map_image"]) if hp_data.get("map_image") else None,
            ))

        # Parse alert tiers
        alert_tiers = []
        tiers_data = day_data.get("alert_tiers", {})
        for tier_key, alert_val in [
            ("major_warning", AlertLevel.MAJOR_WARNING),
            ("warning", AlertLevel.WARNING),
            ("advisory", AlertLevel.ADVISORY),
        ]:
            tier_data = tiers_data.get(tier_key)
            if tier_data is None:
                alert_tiers.append(AlertTierEntry(alert_level=alert_val, text=None))
            elif isinstance(tier_data, dict):
                alert_tiers.append(AlertTierEntry(
                    alert_level=alert_val,
                    text=tier_data.get("text"),
                    recommendations=tier_data.get("recommendations", []),
                ))
            else:
                alert_tiers.append(AlertTierEntry(alert_level=alert_val, text=str(tier_data)))

        # Parse summary map
        summary_map = None
        if day_data.get("summary_map"):
            summary_map = MapImage(file_path=day_data["summary_map"])

        # Parse TMA comment
        tma_comment = None
        tma_data = day_data.get("comments", {}).get("tma")
        if tma_data:
            entries = []
            for entry_data in tma_data.get("entries", []):
                entries.append(AlertCommentEntry(
                    alert_level=AlertLevel(entry_data["alert_level"]),
                    description=entry_data["description"],
                    rating=_parse_rating(entry_data) if entry_data.get("likelihood") else None,
                ))
            tma_comment = TmaComment(entries=entries)

        # Parse MoW comment
        mow_comment = None
        mow_data = day_data.get("comments", {}).get("mow")
        if mow_data:
            entries = []
            for entry_data in mow_data.get("entries", []):
                entries.append(AlertCommentEntry(
                    alert_level=AlertLevel(entry_data["alert_level"]),
                    description=entry_data["description"],
                    rating=_parse_rating(entry_data) if entry_data.get("likelihood") else None,
                ))
            mow_comment = MowComment(entries=entries)

        # Parse DMD comment
        dmd_comment = None
        dmd_data = day_data.get("comments", {}).get("dmd")
        if dmd_data:
            dmd_comment = DmdComment(
                header_text=dmd_data.get("header"),
                impact_bullets=dmd_data.get("bullets", []),
                rating=_parse_rating(dmd_data) if dmd_data.get("likelihood") else None,
            )

        days.append(MultiriskDayForecast(
            forecast_date=forecast_date,
            day_number=day_number,
            hazard_panels=hazard_panels,
            summary_map=summary_map,
            alert_tiers=alert_tiers,
            recommendation_intro=day_data.get("recommendation_intro"),
            recommendations=day_data.get("recommendations", []),
            committee_note=day_data.get("committee_note"),
            tma_comment=tma_comment,
            mow_comment=mow_comment,
            dmd_comment=dmd_comment,
        ))

    # Parse district summaries
    day_summaries = []
    for s_data in data.get("district_summaries", []):
        day_summaries.append(DaySummary(
            day_number=s_data["day_number"],
            major_warning_districts=s_data.get("major_warning", []),
            warning_districts=s_data.get("warning", []),
            advisory_districts=s_data.get("advisory", []),
        ))

    return MultiriskBulletin(
        bulletin_number=data["bulletin_number"],
        issue_date=issue_date,
        issue_time=issue_time,
        language=language,
        days=days,
        day_summaries=day_summaries,
        header_variant=data.get("header_variant", "new"),
    )
