import os

import streamlit as st
from dotenv import load_dotenv

# Locally: copy the values from .env into environment variables.
# On Streamlit Cloud there is no .env file, so this does nothing.
load_dotenv()


def get_setting(name):
    """Read a setting from .env (local) or st.secrets (Streamlit Cloud)."""
    # 1. Local: .env (loaded into environment variables above)
    value = os.getenv(name)
    if value:
        return value

    # 2. Streamlit Cloud: the Secrets box in the app's settings
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass  # no secrets file at all, which is normal when running locally

    raise RuntimeError(
        f"Missing setting {name}. Add it to .env (local) "
        "or to the app's Secrets (Streamlit Cloud)."
    )
