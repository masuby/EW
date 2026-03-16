"""Template management, JSON import/export, session auto-save."""

import json
from datetime import date, time, datetime
from pathlib import Path

import streamlit as st

TEMPLATES_DIR = Path(__file__).parent.parent / "output" / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS_DIR = Path(__file__).parent.parent / "output" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class _Encoder(json.JSONEncoder):
    """JSON encoder that handles date and time objects."""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.strftime("%H:%M")
        if isinstance(obj, frozenset):
            return list(obj)
        return super().default(obj)


def _export_form_state(prefix: str) -> str:
    """Export session state keys matching prefix as JSON."""
    state = {}
    for key, value in st.session_state.items():
        if key.startswith(prefix):
            try:
                json.dumps(value, cls=_Encoder)
                state[key] = value
            except (TypeError, ValueError):
                continue
    return json.dumps(state, indent=2, cls=_Encoder, ensure_ascii=False)


def _import_form_state(json_str: str, prefix: str):
    """Import form state from JSON string into session_state."""
    data = json.loads(json_str)
    for key, value in data.items():
        if key.startswith(prefix):
            st.session_state[key] = value


# --- Templates ---

def save_template(name: str, bulletin_type: str, prefix: str) -> Path:
    """Save current form state as a named template."""
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    path = TEMPLATES_DIR / f"{bulletin_type}_{safe_name}.json"
    path.write_text(_export_form_state(prefix), encoding="utf-8")
    return path


def list_templates(bulletin_type: str) -> list[Path]:
    """List available templates for a bulletin type."""
    return sorted(TEMPLATES_DIR.glob(f"{bulletin_type}_*.json"))


def load_template(path: Path, prefix: str):
    """Load a template into session state."""
    _import_form_state(path.read_text(encoding="utf-8"), prefix)


def render_template_controls(bulletin_type: str, prefix: str):
    """Render save/load template UI in sidebar."""
    with st.sidebar:
        with st.expander("Templates & Export", expanded=False):
            # Save current as template
            tmpl_name = st.text_input(
                "Template name", key=f"{prefix}_tmpl_name",
                placeholder="e.g., rainy_season_default",
            )
            if st.button("Save Template", key=f"{prefix}_tmpl_save",
                         use_container_width=True):
                if tmpl_name:
                    path = save_template(tmpl_name, bulletin_type, prefix)
                    st.success(f"Saved: {path.name}")
                else:
                    st.warning("Enter a template name first.")

            # Load existing template
            templates = list_templates(bulletin_type)
            if templates:
                st.markdown("---")
                tmpl_names = [t.stem.replace(f"{bulletin_type}_", "") for t in templates]
                sel_idx = st.selectbox(
                    "Load template", range(len(tmpl_names)),
                    format_func=lambda i: tmpl_names[i],
                    key=f"{prefix}_tmpl_load_sel",
                )
                if st.button("Load Template", key=f"{prefix}_tmpl_load",
                             use_container_width=True):
                    load_template(templates[sel_idx], prefix)
                    st.success("Template loaded!")
                    st.rerun()

            # Export JSON
            st.markdown("---")
            st.markdown("**Export / Import**")
            json_str = _export_form_state(prefix)
            st.download_button(
                "Export Form as JSON", json_str,
                f"{bulletin_type}_form_state.json",
                "application/json",
                key=f"{prefix}_json_dl",
                use_container_width=True,
            )

            # Import JSON
            uploaded = st.file_uploader(
                "Import JSON", type=["json"],
                key=f"{prefix}_json_import",
            )
            if uploaded:
                _import_form_state(uploaded.read().decode("utf-8"), prefix)
                st.success("Form state imported!")
                st.rerun()


# --- Session Auto-Save ---

def _session_file(username: str, bulletin_type: str) -> Path:
    return SESSIONS_DIR / f"{username}_{bulletin_type}_autosave.json"


def auto_save(username: str, bulletin_type: str, prefix: str):
    """Auto-save current form state for recovery."""
    state_json = _export_form_state(prefix)
    data = json.loads(state_json)
    data["_autosave_timestamp"] = datetime.now().isoformat()
    path = _session_file(username, bulletin_type)
    path.write_text(json.dumps(data, cls=_Encoder, ensure_ascii=False), encoding="utf-8")


def offer_restore(username: str, bulletin_type: str, prefix: str):
    """Show restore prompt if autosaved state exists."""
    restore_key = f"_{prefix}_restore_offered"
    if st.session_state.get(restore_key):
        return

    path = _session_file(username, bulletin_type)
    if not path.exists():
        st.session_state[restore_key] = True
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        timestamp = data.get("_autosave_timestamp", "unknown")
        with st.container(border=True):
            st.info(f"Auto-saved draft found from **{timestamp}**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Restore Draft", key=f"{prefix}_restore_btn",
                             type="primary", use_container_width=True):
                    data.pop("_autosave_timestamp", None)
                    for key, value in data.items():
                        if key.startswith(prefix):
                            st.session_state[key] = value
                    st.session_state[restore_key] = True
                    st.rerun()
            with col2:
                if st.button("Start Fresh", key=f"{prefix}_fresh_btn",
                             use_container_width=True):
                    st.session_state[restore_key] = True
                    st.rerun()
    except (json.JSONDecodeError, OSError):
        st.session_state[restore_key] = True
