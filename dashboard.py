"""Tanzania Early Warning Bulletin Generator — Dashboard.

Run with: streamlit run dashboard.py
"""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.auth import render_login
from dashboard.tma_page import render_tma_page
from dashboard.dmd_page import render_dmd_page
from dashboard.mow_page import render_mow_page
from dashboard.gst_page import render_gst_page
from dashboard.moh_page import render_moh_page
from dashboard.moa_page import render_moa_page
from dashboard.nemc_page import render_nemc_page
from dashboard.history import render_history_panel, render_audit_log

st.set_page_config(
    page_title="Tanzania Early Warning System",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global styles — clean, functional, monospace-accented ──
st.markdown("""
<style>
    /* Header bar */
    .sys-header {
        background: #11223B;
        padding: 16px 20px;
        margin-bottom: 12px;
        border-bottom: 1px solid #0B1728;
    }
    .sys-header-title {
        color: #F7FAFF;
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0;
    }
    .sys-header-sub {
        color: #D0D7E5;
        font-size: 0.9rem;
        margin: 4px 0 0 0;
    }

    /* Status line */
    .sys-status {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        align-items: center;
        padding: 8px 12px;
        background: #FFFFFF;
        border-left: 4px solid #0052CC;
        border-right: 1px solid #E0E4EC;
        border-top: 1px solid #E0E4EC;
        border-bottom: 1px solid #E0E4EC;
        margin-bottom: 14px;
        font-size: 0.88rem;
        color: #2C3A4F;
    }
    .sys-status .ok {
        color: #2E7D32;
        font-weight: 600;
    }
    .sys-status .err {
        color: #C62828;
        font-weight: 600;
    }

    /* Main container padding */
    .block-container {
        padding-top: 0.75rem;
    }

    /* Sidebar panel */
    section[data-testid="stSidebar"] {
        background: #F7F8FB;
        border-right: 1px solid #E0E4EC;
    }
    section[data-testid="stSidebar"] h4 {
        font-size: 1.05rem;
        margin-bottom: 0.25rem;
    }

    /* Insert \"Impact Analysis\" divider above the last radio option (PMO/DMD) */
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label:last-child {
        margin-top: 20px;
        position: relative;
    }
    section[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label:last-child::before {
        content: 'IMPACT ANALYSIS';
        display: block;
        position: absolute;
        top: -20px;
        left: 0;
        right: 0;
        font-size: 0.7rem;
        color: #7A869A;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding-bottom: 3px;
        border-bottom: 1px solid #E0E4EC;
    }
</style>
""", unsafe_allow_html=True)

try:
    from docx2pdf import convert as _docx2pdf_convert  # type: ignore

    _pdf_available = True
except Exception:
    _pdf_available = False

# ── Entity definitions ──
ENTITIES = {
    "TMA — Weather": {
        "header": "TMA // Five Days Severe Weather Forecast",
        "sub": "Tanzania Meteorological Authority — 722E_4 Bulletin Generator",
        "render": render_tma_page,
        "roles": ["tma", "admin"],
    },
    "MoW — Water": {
        "header": "MoW // Flood Risk Assessment",
        "sub": "Ministry of Water — Catchment Basin Analysis",
        "render": render_mow_page,
        "roles": ["mow", "admin"],
    },
    "GST — Geological": {
        "header": "GST // Geological Hazard Monitoring",
        "sub": "Geological Survey of Tanzania — Earthquake, Landslide, Volcano",
        "render": render_gst_page,
        "roles": ["gst", "admin"],
    },
    "MoH — Health": {
        "header": "MoH // Disease Outbreak Monitoring",
        "sub": "Ministry of Health — Epidemic and Outbreak Alerts",
        "render": render_moh_page,
        "roles": ["moh", "admin"],
    },
    "MoA — Agriculture": {
        "header": "MoA // Drought Monitoring",
        "sub": "Ministry of Agriculture — Drought and Food Security",
        "render": render_moa_page,
        "roles": ["moa", "admin"],
    },
    "NEMC — Environment": {
        "header": "NEMC // Air Quality Monitoring",
        "sub": "National Environment Management Council — Air Pollution Alerts",
        "render": render_nemc_page,
        "roles": ["nemc", "admin"],
    },
    "PMO/DMD — Multirisk": {
        "header": "PMO/DMD // Multirisk Impact-Based Forecast",
        "sub": "Prime Minister's Office — Disaster Management Division",
        "render": render_dmd_page,
        "roles": ["dmd", "admin"],
    },
}

ROLE_DEFAULTS = {
    "tma": "TMA — Weather",
    "mow": "MoW — Water",
    "gst": "GST — Geological",
    "moh": "MoH — Health",
    "moa": "MoA — Agriculture",
    "nemc": "NEMC — Environment",
    "dmd": "PMO/DMD — Multirisk",
    "admin": "TMA — Weather",
}


def _status_line(username: str, role: str):
    """Compact system status bar."""
    pdf_cls = "ok" if _pdf_available else "err"
    pdf_txt = "OK" if _pdf_available else "DOCX ONLY"

    st.markdown(f"""
    <div class="sys-status">
        <span>USER: <b>{username}</b> [{role.upper()}]</span>
        <span>PDF ENGINE: <span class="{pdf_cls}">{pdf_txt}</span></span>
        <span>PIPELINE: <span class="ok">READY</span></span>
    </div>
    """, unsafe_allow_html=True)

    if not _pdf_available:
        st.warning(
            "PDF conversion backend not available. Install 'docx2pdf' and ensure "
            "Microsoft Word is installed (on Windows), or switch to DOCX-only output."
        )


def main():
    username, role = render_login()
    if username is None:
        st.stop()
        return

    st.session_state["current_username"] = username
    st.session_state["current_role"] = role

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("---")
        st.markdown("#### Early Warning Entities")

        # Section label: Hazard Information
        st.markdown(
            '<p style="font-family:\'JetBrains Mono\',monospace;font-size:0.7rem;'
            'color:#999;text-transform:uppercase;letter-spacing:0.05em;'
            'margin:12px 0 2px 0;border-bottom:1px solid #e0e0e0;padding-bottom:3px;">'
            'Hazard Information</p>',
            unsafe_allow_html=True,
        )

        options = list(ENTITIES.keys())
        default = ROLE_DEFAULTS.get(role, "TMA — Weather")
        default_idx = options.index(default) if default in options else 0

        view = st.radio(
            "Entity", options=options,
            index=default_idx, key="view_selector",
            label_visibility="collapsed",
            # Custom formatting via CSS below will visually separate Impact Analysis
        )

        st.markdown("---")
        with st.expander("History", expanded=False):
            for key, label in [
                ("tma", "TMA"), ("mow", "MoW"), ("gst", "GST"),
                ("moh", "MoH"), ("moa", "MoA"), ("nemc", "NEMC"),
                ("dmd", "DMD"),
            ]:
                st.caption(label)
                render_history_panel(key)

        if role == "admin":
            with st.expander("Audit Log", expanded=False):
                render_audit_log()

    # ── Header ──
    entity = ENTITIES[view]
    st.markdown(f"""
    <div class="sys-header">
        <p class="sys-header-title">{entity["header"]}</p>
        <p class="sys-header-sub">{entity["sub"]}</p>
    </div>
    """, unsafe_allow_html=True)

    _status_line(username, role)

    # ── Content ──
    entity["render"]()


if __name__ == "__main__":
    main()
