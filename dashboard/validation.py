"""Client-side form validation for the dashboard."""

from dataclasses import dataclass, field

import streamlit as st


@dataclass
class ValidationResult:
    """Result of form validation."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)


def validate_tma_form(issue_date, issue_time, day_data: list[dict]) -> ValidationResult:
    """Validate TMA 722E_4 form before generation."""
    result = ValidationResult()

    if not issue_date:
        result.add_error("Issue date is required.")
    if not issue_time:
        result.add_error("Issue time is required.")

    has_any_hazard = False
    for d, dd in enumerate(day_data):
        if dd.get("no_warning"):
            continue
        for h_idx, h in enumerate(dd.get("hazards", [])):
            has_any_hazard = True
            if not h.get("regions"):
                result.add_error(f"Day {d+1}, Hazard {h_idx+1}: No regions selected.")
            if not h.get("description", "").strip():
                result.add_warning(f"Day {d+1}, Hazard {h_idx+1}: Description is empty.")
            if not h.get("impacts_expected", "").strip():
                result.add_warning(f"Day {d+1}, Hazard {h_idx+1}: Impacts expected is empty.")

    if not has_any_hazard:
        result.add_warning("All days are set to No Warning. Is this intentional?")

    return result


def validate_dmd_form(form: dict) -> ValidationResult:
    """Validate DMD Multirisk form before generation."""
    result = ValidationResult()

    if not form.get("issue_date"):
        result.add_error("Issue date is required.")
    if not form.get("issue_time"):
        result.add_error("Issue time is required.")

    has_any_districts = False
    for d in range(3):
        tiers = form.get(f"day{d}_tiers", {})
        day_total = sum(len(v) for v in tiers.values())
        if day_total > 0:
            has_any_districts = True

        recs = form.get(f"day{d}_recommendations", [])
        if day_total > 0 and not recs:
            result.add_warning(f"Day {d+1}: Districts selected but no recommendations provided.")

        tma_entries = form.get(f"day{d}_tma_entries", [])
        if day_total > 0 and not tma_entries:
            result.add_warning(f"Day {d+1}: No TMA comments provided.")

    if not has_any_districts:
        result.add_warning("No districts selected for any day. Is this intentional?")

    return result


def render_validation_results(result: ValidationResult) -> bool:
    """Render validation errors and warnings. Returns True if valid."""
    if result.errors:
        for err in result.errors:
            st.error(err)
    if result.warnings:
        for warn in result.warnings:
            st.warning(warn)
    return result.valid
