"""TMA Dashboard — 722E_4 Five Days Severe Weather Forecast.

Interactive plotly map with click-to-select regions.
Multiselect as backup/search input, synced with map.
Includes: validation, copy-day, templates, progress, audit logging.
"""

import json
import io
import contextlib
from datetime import date, time, timedelta, datetime
from pathlib import Path

import streamlit as st

from .config import (
    TMA_OUTPUT_DIR, DOCUMENTS_DIR, OUTPUT_DIR,
    ALERT_LEVELS, DEFAULT_COLORS, get_raw_region_name,
    get_region_names, HAZARD_TYPES, LIKELIHOOD_LEVELS, IMPACT_LEVELS,
    DEFAULT_IMPACTS_EXPECTED,
)
from .map_widget import render_map_selector
from .pdf_viewer import render_pdf_preview, render_side_by_side, get_pdf_pages
from .validation import validate_tma_form, render_validation_results
from .templates import render_template_controls, auto_save, offer_restore


ALERT_COLOR_MAP = {a["key"]: a["color"] for a in ALERT_LEVELS}


def _alert_badge(level_key: str):
    info = next((a for a in ALERT_LEVELS if a["key"] == level_key), None)
    if not info:
        return
    bg = info["color"]
    tc = "#000" if level_key in ("NO_WARNING", "ADVISORY") else "#FFF"
    st.markdown(
        f'<span style="background:{bg};color:{tc};padding:4px 14px;'
        f'border-radius:4px;font-weight:bold;font-size:13px;">'
        f'{info["label"]}</span>',
        unsafe_allow_html=True,
    )


def _copy_day_data(source_day: int, target_day: int):
    """Copy all form data from source day to target day in session_state."""
    src = f"tma_d{source_day}"
    tgt = f"tma_d{target_day}"

    # Copy no_warning checkbox
    if f"{src}_nowarning" in st.session_state:
        st.session_state[f"{tgt}_nowarning"] = st.session_state[f"{src}_nowarning"]

    # Copy hazard count
    src_count = st.session_state.get(f"{src}_haz_count", 1)
    st.session_state[f"{tgt}_haz_count"] = src_count

    # Copy each hazard's fields
    for h in range(src_count):
        for suffix in ["_type", "_alert", "_desc", "_lik", "_imp",
                       "_impacts", "_regions", "_districts",
                       "_mode", "_show_dist", "_geo_level"]:
            src_key = f"{src}_h{h}{suffix}"
            tgt_key = f"{tgt}_h{h}{suffix}"
            if src_key in st.session_state:
                st.session_state[tgt_key] = st.session_state[src_key]


def _collect_day_data(day_idx: int) -> dict:
    prefix = f"tma_d{day_idx}"
    all_regions = get_region_names()

    # Copy-from-day button (Days 2-5)
    if day_idx > 0:
        copy_col1, copy_col2 = st.columns([4, 1])
        with copy_col2:
            copy_src = st.selectbox(
                "Copy from",
                [f"Day {i+1}" for i in range(day_idx)],
                key=f"{prefix}_copy_src",
            )
            if st.button("Copy", key=f"{prefix}_copy_btn", use_container_width=True):
                src_idx = int(copy_src.split()[-1]) - 1
                _copy_day_data(src_idx, day_idx)
                st.rerun()

    no_warning = st.checkbox(
        "No Warning for this day",
        value=(day_idx == 0 or day_idx == 4),
        key=f"{prefix}_nowarning",
    )
    if no_warning:
        return {"hazards": [], "no_warning": True}

    hazards = []
    haz_count_key = f"{prefix}_haz_count"
    if haz_count_key not in st.session_state:
        st.session_state[haz_count_key] = 1

    for h in range(st.session_state[haz_count_key]):
        st.markdown("---")
        st.markdown(f"#### Hazard {h + 1}")

        # Type + Alert Level + Badge
        hcol1, hcol2, hcol3 = st.columns([2, 2, 1])
        with hcol1:
            htype_idx = st.selectbox(
                "Hazard Type", range(len(HAZARD_TYPES)),
                format_func=lambda i: HAZARD_TYPES[i]["label"],
                key=f"{prefix}_h{h}_type",
            )
            htype = HAZARD_TYPES[htype_idx]["key"]
        with hcol2:
            levels = ALERT_LEVELS[1:]
            alert_idx = st.selectbox(
                "Alert Level", range(len(levels)),
                format_func=lambda i: levels[i]["label"],
                key=f"{prefix}_h{h}_alert",
            )
            alert = levels[alert_idx]["key"]
        with hcol3:
            st.markdown("&nbsp;")
            _alert_badge(alert)

        # Region/District selection — unified widget
        alert_color = ALERT_COLOR_MAP.get(alert, "#FFFF00")
        regions_key = f"{prefix}_h{h}_regions"

        selection = render_map_selector(
            key_prefix=f"{prefix}_h{h}",
            sel_key=regions_key,
            color=alert_color,
            all_regions=all_regions,
            allow_districts=True,
        )
        selected_regions = selection["regions"]
        selected_districts = selection["districts"]

        # Description with tooltip
        desc_placeholder = DEFAULT_IMPACTS_EXPECTED.get(htype, {}).get("en", "")
        desc = st.text_area(
            "Description", key=f"{prefix}_h{h}_desc", height=80,
            placeholder="of heavy rain is issued over few areas of the Lake Victoria Basin...",
            help="Describe the hazard forecast. Starts with lowercase 'of' as it follows the alert level label in the final document.",
        )

        # Likelihood & Impact
        lcol1, lcol2 = st.columns(2)
        with lcol1:
            lik = st.selectbox("Likelihood", LIKELIHOOD_LEVELS, index=1,
                               key=f"{prefix}_h{h}_lik")
        with lcol2:
            imp = st.selectbox("Impact", IMPACT_LEVELS, index=1,
                               key=f"{prefix}_h{h}_imp")

        # Impacts Expected with tooltip
        default_impact = DEFAULT_IMPACTS_EXPECTED.get(htype, {}).get("en", "")
        impacts_exp = st.text_area(
            "Impacts Expected", key=f"{prefix}_h{h}_impacts", height=68,
            placeholder=default_impact or "Localized floods over few areas.",
            help="Describe expected impacts on communities and infrastructure.",
        )

        # Build region list — include both directly selected regions and
        # parent regions of selected districts
        all_selected_regions = set(get_raw_region_name(r) for r in selected_regions)

        hazards.append({
            "type": htype,
            "alert_level": alert,
            "description": desc,
            "regions": sorted(all_selected_regions),
            "districts": sorted(selected_districts),
            "drawn_shapes": selection.get("drawn_shapes", []),
            "likelihood": lik,
            "impact": imp,
            "impacts_expected": impacts_exp,
        })

    # Add/remove hazard
    acol1, acol2 = st.columns(2)
    with acol1:
        if st.button("+ Add Hazard", key=f"{prefix}_add_haz",
                     use_container_width=True, type="primary"):
            st.session_state[haz_count_key] += 1
            st.rerun()
    with acol2:
        if st.session_state[haz_count_key] > 1:
            if st.button("- Remove Hazard", key=f"{prefix}_rem_haz",
                         use_container_width=True):
                st.session_state[haz_count_key] -= 1
                st.rerun()

    return {"hazards": hazards, "no_warning": False}


def _build_json(issue_date: date, issue_time: time, day_data: list[dict]) -> dict:
    days = []
    for d, dd in enumerate(day_data):
        forecast_date = issue_date + timedelta(days=d)
        day_json = {"date": forecast_date.strftime("%Y-%m-%d"), "hazards": []}
        if not dd["no_warning"]:
            for h in dd["hazards"]:
                hazard = {"type": h["type"], "alert_level": h["alert_level"]}
                for field in ("description", "regions", "likelihood", "impact", "impacts_expected", "drawn_shapes"):
                    if h.get(field):
                        hazard[field] = h[field]
                day_json["hazards"].append(hazard)
        days.append(day_json)
    return {
        "issue_date": issue_date.strftime("%Y-%m-%d"),
        "issue_time": issue_time.strftime("%H:%M"),
        "days": days,
    }


def _run_generation(json_data: dict) -> dict:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.pipeline import generate_722e4

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_path = OUTPUT_DIR / f"_tma_input_{timestamp}.json"
    tmp_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False))

    log_buf = io.StringIO()
    start = datetime.now()
    try:
        with contextlib.redirect_stdout(log_buf):
            result = generate_722e4(
                input_path=str(tmp_path),
                output_dir=str(TMA_OUTPUT_DIR),
                output_format="both",
                auto_maps=True,
            )
        duration = (datetime.now() - start).total_seconds()
        return {"result": result, "logs": log_buf.getvalue(),
                "error": None, "duration": duration}
    except Exception as e:
        import traceback
        duration = (datetime.now() - start).total_seconds()
        return {"result": None, "logs": log_buf.getvalue(),
                "error": traceback.format_exc(), "duration": duration}
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _render_error(gen_result: dict):
    """Render generation error with specific recovery suggestions."""
    st.error("Generation failed!")
    error_text = gen_result["error"]

    if "LibreOffice" in error_text or "libreoffice" in error_text:
        st.warning(
            "PDF conversion requires LibreOffice. The DOCX may still exist. "
            "Install: `sudo apt install libreoffice`"
        )
    elif "ValidationError" in error_text or "ValueError" in error_text:
        st.warning("Input data validation failed. Check all required fields are filled.")
    elif "FileNotFoundError" in error_text:
        st.warning("A required file was not found. Check geodata files in assets/geodata/.")

    with st.expander("Technical Details", expanded=False):
        st.code(error_text, language="text")
    with st.expander("Generation Log", expanded=False):
        st.code(gen_result.get("logs", ""), language="text")


def render_tma_page():
    # Session restore
    username = st.session_state.get("current_username", "unknown")
    offer_restore(username, "tma", "tma")

    # Template controls in sidebar
    render_template_controls("tma", "tma")

    # Issue info
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            issue_date = st.date_input("Issue Date", value=date.today(),
                                       key="tma_issue_date")
        with col2:
            issue_time = st.time_input("Issue Time", value=time(15, 30),
                                       key="tma_issue_time")

    # Alert legend
    with st.container(border=True):
        st.markdown("**Alert Level Legend:**")
        lcols = st.columns(4)
        for i, level in enumerate(ALERT_LEVELS):
            with lcols[i]:
                bg = level["color"]
                tc = "#000" if level["key"] in ("NO_WARNING", "ADVISORY") else "#FFF"
                st.markdown(
                    f'<div style="background:{bg};color:{tc};padding:8px;'
                    f'border-radius:6px;text-align:center;font-weight:bold;">'
                    f'{level["label"]}</div>',
                    unsafe_allow_html=True,
                )

    # Day tabs
    day_labels = [
        f"Day {d+1} ({(issue_date + timedelta(days=d)).strftime('%a %d/%m')})"
        for d in range(5)
    ]
    tabs = st.tabs(day_labels)
    all_day_data = []
    for d, tab in enumerate(tabs):
        with tab:
            all_day_data.append(_collect_day_data(d))

    st.markdown("---")

    # --- Validation + Generate ---
    if st.button("Generate 722E_4 Bulletin", type="primary",
                 use_container_width=True, key="tma_generate"):
        validation = validate_tma_form(issue_date, issue_time, all_day_data)
        if not render_validation_results(validation):
            st.stop()

        json_data = _build_json(issue_date, issue_time, all_day_data)

        # Progress bar
        progress = st.progress(0, text="Preparing...")
        progress.progress(15, text="Generating maps and document...")

        gen_result = _run_generation(json_data)
        st.session_state["tma_gen_result"] = gen_result

        # Save TMA data for DMD auto-import (session + file)
        from .data_bridge import save_tma_for_dmd
        save_tma_for_dmd(json_data)

        progress.progress(100, text="Complete!")

        # Auto-save
        auto_save(username, "tma", "tma")

        # Audit log
        from .audit import log_generation
        log_generation(
            username, st.session_state.get("current_role", "unknown"),
            "722e4", json_data, gen_result, gen_result["duration"],
        )

    # --- Results ---
    gen_result = st.session_state.get("tma_gen_result")
    if not gen_result:
        return

    st.markdown("---")
    if gen_result["error"]:
        _render_error(gen_result)
        return

    # Success metrics
    result = gen_result.get("result", {})
    pdf_path = result.get("pdf")
    docx_path = result.get("docx")

    st.success(f"Bulletin generated successfully!")

    # Metadata cards
    meta_cols = st.columns(4)
    with meta_cols[0]:
        st.metric("Generation Time", f"{gen_result['duration']:.1f}s")
    with meta_cols[1]:
        if pdf_path and Path(pdf_path).exists():
            pages = get_pdf_pages(pdf_path)
            st.metric("PDF Pages", len(pages))
    with meta_cols[2]:
        if pdf_path and Path(pdf_path).exists():
            st.metric("PDF Size", f"{Path(pdf_path).stat().st_size / 1024:.0f} KB")
    with meta_cols[3]:
        if docx_path and Path(docx_path).exists():
            st.metric("DOCX Size", f"{Path(docx_path).stat().st_size / 1024:.0f} KB")

    with st.expander("Generation Log", expanded=False):
        st.code(gen_result.get("logs", ""), language="text")

    if not pdf_path or not Path(pdf_path).exists():
        return

    tab_preview, tab_compare, tab_download = st.tabs([
        "Preview", "Compare with Reference", "Download",
    ])
    with tab_preview:
        render_pdf_preview(pdf_path, "Generated Bulletin", key_prefix="tma_preview")
    with tab_compare:
        refs = sorted(DOCUMENTS_DIR.glob("722E_4*.pdf"))
        if refs:
            ref_names = [r.name for r in refs]
            sel = st.selectbox("Reference", ref_names,
                               index=len(ref_names) - 1, key="tma_ref_sel")
            render_side_by_side(pdf_path, str(DOCUMENTS_DIR / sel),
                                key_prefix="tma_cmp")
        else:
            st.info("No reference PDFs in documents/")
    with tab_download:
        col1, col2 = st.columns(2)
        with col1:
            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    st.download_button("Download PDF", f.read(),
                                       Path(pdf_path).name, "application/pdf",
                                       use_container_width=True)
        with col2:
            if docx_path and Path(docx_path).exists():
                with open(docx_path, "rb") as f:
                    st.download_button("Download DOCX", f.read(),
                                       Path(docx_path).name,
                                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                       use_container_width=True)

    # --- Link to PMO/DMD Dashboard ---
    st.markdown("---")
    with st.container(border=True):
        st.markdown(
            '<div style="display:flex;align-items:center;gap:0.5rem;">'
            '<span style="font-size:1.3rem;">&#10145;</span>'
            '<span style="font-size:1rem;font-weight:600;">'
            "Proceed to PMO/DMD Multirisk Bulletin</span></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "TMA forecast data will be available for import in the DMD page "
            "to pre-fill districts and comments automatically."
        )
        if st.button(
            "Go to PMO/DMD Dashboard",
            type="primary",
            use_container_width=True,
            key="tma_goto_dmd",
        ):
            st.session_state["view_selector"] = "PMO/DMD (Multirisk)"
            st.rerun()
