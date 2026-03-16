"""Shared visual form components — color pickers, visual selectors, dynamic lists."""

from datetime import date, time

import streamlit as st

from .config import (
    ALERT_LEVELS, HAZARD_TYPES,
    LIKELIHOOD_LEVELS, IMPACT_LEVELS,
    DEFAULT_COLORS,
    get_region_names, get_district_names, get_districts_by_region,
)


# --- Color Pickers ---

def alert_color_pickers(key_prefix: str = "colors") -> dict[str, str]:
    """Render color pickers for each alert level. Returns dict of level -> hex color."""
    st.markdown("**Alert Level Colors**")
    cols = st.columns(3)
    colors = {}
    for i, level in enumerate(ALERT_LEVELS[1:]):  # Skip NO_WARNING
        with cols[i]:
            colors[level["key"]] = st.color_picker(
                level["label"],
                value=level["color"],
                key=f"{key_prefix}_{level['key']}",
            )
    return colors


# --- Visual Selectors ---

def alert_level_select(label: str = "Alert Level", key: str = "alert",
                       include_no_warning: bool = True) -> str:
    """Alert level dropdown with inline color badge."""
    levels = ALERT_LEVELS if include_no_warning else ALERT_LEVELS[1:]
    options = [a["key"] for a in levels]
    labels = [a["label"] for a in levels]

    idx = st.selectbox(label, range(len(labels)),
                       format_func=lambda i: labels[i], key=key)
    selected = options[idx]

    # Inline color badge
    info = levels[idx]
    bg = info["color"]
    tc = "#000" if selected in ("NO_WARNING", "ADVISORY") else "#FFF"
    st.markdown(
        f'<span style="background:{bg};color:{tc};padding:2px 10px;'
        f'border-radius:3px;font-size:12px;font-weight:bold;">'
        f'{info["label"]}</span>',
        unsafe_allow_html=True,
    )
    return selected


def hazard_type_select(label: str = "Hazard Type", key: str = "hazard") -> str:
    """Hazard type dropdown."""
    options = [h["key"] for h in HAZARD_TYPES]
    labels = [h["label"] for h in HAZARD_TYPES]
    idx = st.selectbox(label, range(len(labels)),
                       format_func=lambda i: labels[i], key=key)
    return options[idx]


def likelihood_impact_row(key_prefix: str = "rating") -> tuple[str, str]:
    """Two-column Likelihood and Impact dropdowns."""
    col1, col2 = st.columns(2)
    with col1:
        likelihood = st.selectbox(
            "Likelihood", LIKELIHOOD_LEVELS, index=1,
            key=f"{key_prefix}_lik",
        )
    with col2:
        impact = st.selectbox(
            "Impact", IMPACT_LEVELS, index=1,
            key=f"{key_prefix}_imp",
        )
    return likelihood, impact


# --- Region/District Selection ---

def region_selector(key_prefix: str = "reg",
                    label: str = "Select Regions") -> list[str]:
    """Multi-select for regions with 'Select All' / 'Clear' buttons."""
    all_regions = get_region_names()

    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        st.markdown(f"**{label}**")
    with col2:
        if st.button("All", key=f"{key_prefix}_all", use_container_width=True):
            st.session_state[f"{key_prefix}_selected"] = list(all_regions)
            st.rerun()
    with col3:
        if st.button("Clear", key=f"{key_prefix}_clear", use_container_width=True):
            st.session_state[f"{key_prefix}_selected"] = []
            st.rerun()

    default = st.session_state.get(f"{key_prefix}_selected", [])
    selected = st.multiselect(
        label, all_regions, default=default,
        key=f"{key_prefix}_ms",
        label_visibility="collapsed",
    )
    st.session_state[f"{key_prefix}_selected"] = selected
    return selected


def district_selector_by_tier(key_prefix: str = "dist",
                              tier_label: str = "Districts") -> dict[str, list[str]]:
    """Three-tier district selector: Major Warning, Warning, Advisory.

    Uses canonical session state keys (key_prefix + tier_key) so that
    external code (e.g. interactive map) can modify them and multiselects
    stay in sync.

    Returns dict with keys 'major_warning', 'warning', 'advisory' -> list of district names.
    """
    all_districts = get_district_names()
    by_region = get_districts_by_region()

    result = {}
    tier_config = [
        ("major_warning", "Major Warning", "red"),
        ("warning", "Warning", "orange"),
        ("advisory", "Advisory", "blue"),
    ]

    for tier_key, tier_label_text, emoji_color in tier_config:
        canonical_key = f"{key_prefix}_{tier_key}"
        if canonical_key not in st.session_state:
            st.session_state[canonical_key] = []

        with st.expander(
            f":{emoji_color}[{tier_label_text}] Districts "
            f"({len(st.session_state[canonical_key])})",
            expanded=False,
        ):
            # Region-based quick select
            st.caption("Quick select by region:")
            region_cols = st.columns(4)
            region_names = sorted(by_region.keys())

            for i, region in enumerate(region_names):
                col_idx = i % 4
                with region_cols[col_idx]:
                    if st.button(
                        region, key=f"{key_prefix}_{tier_key}_reg_{region}",
                        use_container_width=True,
                    ):
                        current = list(st.session_state.get(canonical_key, []))
                        for d in by_region[region]:
                            if d not in current:
                                current.append(d)
                        st.session_state[canonical_key] = current
                        st.rerun()

            # Multi-select — bound directly to canonical key
            selected = st.multiselect(
                f"{tier_label_text} districts",
                all_districts,
                key=canonical_key,
            )
            result[tier_key] = selected

    return result


# --- Dynamic Text Lists ---

def dynamic_text_list(label: str, key_prefix: str,
                      default_items: list = None,
                      placeholder: str = "") -> list[str]:
    """Dynamic list of text inputs with add/remove."""
    count_key = f"{key_prefix}_count"
    if count_key not in st.session_state:
        st.session_state[count_key] = max(len(default_items or []), 1)

    st.markdown(f"**{label}**")
    items = []
    for i in range(st.session_state[count_key]):
        default_val = ""
        if default_items and i < len(default_items):
            default_val = default_items[i]
        val = st.text_area(
            f"Item {i + 1}",
            value=default_val,
            height=68,
            key=f"{key_prefix}_{i}",
            label_visibility="collapsed",
            placeholder=placeholder,
        )
        if val.strip():
            items.append(val.strip())

    col1, col2 = st.columns(2)
    with col1:
        if st.button("+ Add", key=f"{key_prefix}_add"):
            st.session_state[count_key] += 1
            st.rerun()
    with col2:
        if st.session_state[count_key] > 1:
            if st.button("- Remove", key=f"{key_prefix}_rem"):
                st.session_state[count_key] -= 1
                st.rerun()

    return items


# --- Status Indicators ---

def status_badge(text: str, color: str = "green"):
    """Display a colored status badge."""
    st.markdown(
        f'<span style="background-color:{color};color:white;padding:4px 12px;'
        f'border-radius:12px;font-size:13px;font-weight:bold;">{text}</span>',
        unsafe_allow_html=True,
    )


def alert_level_badge(level: str):
    """Display an alert level badge with appropriate color."""
    level_info = next((a for a in ALERT_LEVELS if a["key"] == level), None)
    if level_info:
        bg = level_info["color"]
        text_color = "#000" if level in ("NO_WARNING", "ADVISORY") else "#FFF"
        st.markdown(
            f'<span style="background-color:{bg};color:{text_color};padding:4px 12px;'
            f'border-radius:4px;font-weight:bold;">{level_info["label"]}</span>',
            unsafe_allow_html=True,
        )
