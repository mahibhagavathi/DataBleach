import streamlit as st
from utils.session import init_session
from views.landing import show_landing
from views.analysis import show_analysis
from views.fixing import show_fixing
from views.results import show_results

st.set_page_config(
    page_title="DataDoctor",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject global CSS
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; }
    .stProgress > div > div { border-radius: 10px; }
    div[data-testid="metric-container"] {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 1rem;
    }
    .issue-card {
        background: #ffffff;
        border: 1px solid #dee2e6;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .severity-critical { border-left: 5px solid #dc3545; }
    .severity-high     { border-left: 5px solid #fd7e14; }
    .severity-medium   { border-left: 5px solid #ffc107; }
    .severity-low      { border-left: 5px solid #0d6efd; }
    .phase-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

init_session()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🩺 DataDoctor")
    st.caption("AI-powered data cleaning assistant")
    st.divider()

    phase = st.session_state.phase
    phases = ["📥 Input", "🔍 Analysis", "🛠️ Fixing", "✅ Results"]
    phase_map = {"input": 0, "analysis": 1, "fixing": 2, "results": 3}
    current = phase_map.get(phase, 0)

    for i, p in enumerate(phases):
        if i < current:
            st.markdown(f"~~{p}~~ ✓")
        elif i == current:
            st.markdown(f"**→ {p}**")
        else:
            st.markdown(f"<span style='color:#aaa'>{p}</span>", unsafe_allow_html=True)

    if phase in ("fixing", "results") and st.session_state.issues:
        st.divider()
        total = len(st.session_state.issues)
        reviewed = sum(1 for iss in st.session_state.issues if iss.get("decision"))
        st.markdown(f"**Progress:** {reviewed}/{total} issues reviewed")
        st.progress(reviewed / total if total else 0)

        st.divider()
        st.markdown("**Change Log**")
        for iss in st.session_state.issues:
            d = iss.get("decision")
            if d == "apply":
                st.markdown(f"✅ #{iss['id']} {iss['column']} — Applied")
            elif d == "skip":
                st.markdown(f"❌ #{iss['id']} {iss['column']} — Skipped")
            elif d == "custom":
                st.markdown(f"✏️ #{iss['id']} {iss['column']} — Custom")

    if st.session_state.df_raw is not None:
        st.divider()
        df = st.session_state.df_raw
        st.markdown(f"**Dataset:** {st.session_state.dataset_name}")
        st.markdown(f"Rows: `{df.shape[0]:,}` · Cols: `{df.shape[1]}`")

    st.divider()
    if st.button("🔄 Start Over", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        init_session()
        st.rerun()

# ── Route to current phase view ───────────────────────────────────────────────
if phase == "input":
    show_landing()
elif phase == "analysis":
    show_analysis()
elif phase == "fixing":
    show_fixing()
elif phase == "results":
    show_results()
