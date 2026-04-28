import streamlit as st
import pandas as pd
from utils.demo_data import DEMO_DATASETS, load_demo


def show_landing():
    st.title("🩺 DataDoctor")
    st.markdown("#### AI-powered data cleaning assistant — upload your dataset and get a full quality report in seconds.")
    st.divider()

    tab_upload, tab_demo = st.tabs(["📁 Upload Your CSV", "🎯 Use a Demo Dataset"])

    with tab_upload:
        st.markdown("**Drag and drop your CSV file below.**")
        st.caption("Supports CSV files up to 200 MB. Your data never leaves your session.")
        uploaded = st.file_uploader("", type=["csv"], label_visibility="collapsed")

        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                if len(df) > 100_000:
                    st.warning(f"Large file detected ({len(df):,} rows). Sampling 50,000 rows for analysis.")
                    df = df.sample(50_000, random_state=42).reset_index(drop=True)

                # Only set if this is a new file
                if st.session_state.dataset_name != uploaded.name:
                    st.session_state.df_raw     = df
                    st.session_state.df_clean   = df.copy()
                    st.session_state.dataset_name = uploaded.name

                _show_preview(st.session_state.df_raw)

                if st.button("🔍 Analyze My Data", type="primary", use_container_width=True):
                    st.session_state.phase = "analysis"
                    st.rerun()

            except Exception as e:
                st.error(f"Could not read file: {e}. Please ensure it is a valid CSV.")

    with tab_demo:
        st.markdown("**No dataset handy? Pick one of our pre-loaded examples.**")
        st.caption("Pre-seeded with realistic data quality issues across all severity levels.")

        choice = st.selectbox("Choose a demo dataset:", list(DEMO_DATASETS.keys()))

        if st.button("Load Demo Dataset", use_container_width=True):
            key = DEMO_DATASETS[choice]
            df  = load_demo(key)
            # Always load fresh — user explicitly clicked Load
            st.session_state.df_raw       = df
            st.session_state.df_clean     = df.copy()
            st.session_state.dataset_name = choice
            st.session_state.issues       = []   # reset any prior analysis
            st.session_state.current_issue_idx = 0
            st.rerun()

        if st.session_state.df_raw is not None:
            _show_preview(st.session_state.df_raw)
            if st.button("🔍 Analyze This Dataset", type="primary", use_container_width=True):
                st.session_state.phase = "analysis"
                st.rerun()


def _show_preview(df: pd.DataFrame):
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("Rows",           f"{df.shape[0]:,}")
    col2.metric("Columns",        df.shape[1])
    col3.metric("Missing Values", f"{df.isna().sum().sum():,}")
    st.markdown("**Preview (first 5 rows)**")
    st.dataframe(df.head(), use_container_width=True)
