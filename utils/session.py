import streamlit as st


def init_session():
    defaults = {
        "phase": "input",
        "df_raw": None,
        "df_clean": None,
        "dataset_name": None,
        "issues": [],
        "current_issue_idx": 0,
        "health_score_before": None,
        "health_score_after": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
