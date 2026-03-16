"""Bulletin history browser and audit log viewer."""

from pathlib import Path
from datetime import datetime

import streamlit as st

from .config import TMA_OUTPUT_DIR, DMD_OUTPUT_DIR
from .pdf_viewer import get_pdf_pages
from .audit import get_audit_entries


def _get_bulletin_files(output_dir: Path) -> list[dict]:
    """Scan output directory for generated bulletin files."""
    files = []
    for pdf in sorted(output_dir.glob("*.pdf"), reverse=True):
        docx = pdf.with_suffix(".docx")
        stat = pdf.stat()
        files.append({
            "name": pdf.stem,
            "pdf_path": str(pdf),
            "docx_path": str(docx) if docx.exists() else None,
            "pdf_size_kb": stat.st_size / 1024,
            "docx_size_kb": docx.stat().st_size / 1024 if docx.exists() else 0,
            "created": datetime.fromtimestamp(stat.st_mtime),
        })
    return files


def render_history_panel(bulletin_type: str):
    """Render bulletin history panel."""
    if bulletin_type == "tma":
        output_dir = TMA_OUTPUT_DIR
        label = "TMA 722E_4"
    else:
        output_dir = DMD_OUTPUT_DIR
        label = "DMD Multirisk"

    files = _get_bulletin_files(output_dir)
    if not files:
        st.caption(f"No {label} bulletins generated yet.")
        return

    st.caption(f"{len(files)} bulletin(s)")

    for f in files:
        with st.expander(
            f"{f['name']} ({f['created'].strftime('%d/%m %H:%M')})",
            expanded=False,
        ):
            st.caption(
                f"PDF: {f['pdf_size_kb']:.0f} KB | "
                f"DOCX: {f['docx_size_kb']:.0f} KB"
            )

            # Download buttons
            col1, col2 = st.columns(2)
            with col1:
                with open(f["pdf_path"], "rb") as fp:
                    st.download_button(
                        "PDF", fp.read(),
                        Path(f["pdf_path"]).name, "application/pdf",
                        key=f"hist_{bulletin_type}_{f['name']}_pdf",
                        use_container_width=True,
                    )
            with col2:
                if f["docx_path"]:
                    with open(f["docx_path"], "rb") as fp:
                        st.download_button(
                            "DOCX", fp.read(),
                            Path(f["docx_path"]).name,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"hist_{bulletin_type}_{f['name']}_docx",
                            use_container_width=True,
                        )


def render_audit_log():
    """Render recent audit log entries."""
    entries = get_audit_entries(limit=30)
    if not entries:
        st.caption("No generation events recorded yet.")
        return

    for entry in entries:
        ok = entry.get("success", False)
        color = "#28a745" if ok else "#dc3545"
        status = "OK" if ok else "FAIL"
        st.markdown(
            f'<div style="border-left:3px solid {color};padding:3px 10px;margin:3px 0;font-size:0.85rem;">'
            f'<strong>{entry.get("bulletin_type", "?").upper()}</strong> | '
            f'{entry.get("username", "?")} | '
            f'{entry.get("issue_date", "?")} | '
            f'{entry.get("duration_seconds", 0):.1f}s | '
            f'<span style="color:{color}">{status}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
