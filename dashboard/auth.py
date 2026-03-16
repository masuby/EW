"""Authentication and role-based access for the dashboard."""

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "dashboard_config.yaml"


def load_auth_config() -> dict:
    """Load authentication configuration from YAML."""
    if not CONFIG_PATH.exists():
        st.error(f"Config file not found: {CONFIG_PATH}")
        st.stop()
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_authenticator(config: dict):
    """Create and return a streamlit-authenticator instance."""
    return stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )


def get_user_role(config: dict, username: str) -> str:
    """Get the role for a given username."""
    users = config.get("credentials", {}).get("usernames", {})
    user_info = users.get(username, {})
    return user_info.get("role", "unknown")


def render_login() -> tuple[str | None, str | None]:
    """Render login form and return (username, role) or (None, None).

    Returns:
        Tuple of (username, role) if authenticated, else (None, None).
    """
    config = load_auth_config()
    authenticator = get_authenticator(config)

    authenticator.login(location="main")

    if st.session_state.get("authentication_status"):
        username = st.session_state.get("username", "")
        role = get_user_role(config, username)

        # Sidebar: user info + logout
        with st.sidebar:
            st.markdown(f"**{st.session_state.get('name', username)}**")
            st.caption(f"Role: {role.upper()}")
            authenticator.logout("Logout", "sidebar")

        return username, role

    elif st.session_state.get("authentication_status") is False:
        st.error("Invalid username or password")
        return None, None

    else:
        # Not yet attempted
        return None, None
