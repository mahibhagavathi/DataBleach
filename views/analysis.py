import streamlit as st
import time
import pandas as pd
from utils.detector import detect_issues, compute_health_score
from utils.ai import enrich_issue_with_ai

SEVERITY_EMOJI  = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
SEVERITY_COLOR  = {"critical": "#dc3545", "high": "#fd7e14", "medium": "#e6a817", "low": "0d6efd"}
SEVERITY_BG     = {"critical": "#fff5f5", "high": "#fff8f0", "medium": "#fffdf0", "low": "#f0f4ff"}


def show_analysis():
    if not st.session_state.issues:
        _run_analysis(st.session_state.df_raw)
    else:
        _show_scorecard()


def _run_analysis(df):
    st.title("🔍 Analysing Your Dataset...")
    progress = st.progress(0)
    status   = st.empty()
    steps = [
        (0.15, "Scanning for structural issues..."),
        (0.30, "Checking duplicates & key integrity..."),
        (0.50, "Detecting missing values & type errors..."),
        (0.65, "Identifying outliers & impossible values..."),
        (0.80, "Checking formatting consistency..."),
        (0.90, "Asking Gemini AI for insights..."),
    ]
    for pct, msg in steps:
        status.info(f"⏳ {msg}")
        progress.progress(pct)
        time.sleep(0.3)

    issues      = detect_issues(df)
    score_before = compute_health_score(issues)
    st.session_state.health_score_before = score_before

    # AI enrich first 15
    ai_sample = issues[:15]
    for i, iss in enumerate(ai_sample):
        issues[i] = enrich_issue_with_ai(iss)
        progress.progress(0.90 + 0.10 * ((i + 1) / len(ai_sample)))

    for iss in issues[15:]:
        iss["ai_explanation"] = iss["detected"]
        iss["ai_risk"]        = "May cause errors or skewed results in downstream analysis."
        iss["ai_confidence"]  = "N/A"

    st.session_state.issues            = issues
    st.session_state.health_score_after = score_before
    status.success("✅ Analysis complete!")
    progress.progress(1.0)
    time.sleep(0.4)
    st.rerun()


def _show_scorecard():
    issues = st.session_state.issues
    score  = st.session_state.health_score_before

    st.title("📋 Data Health Report")

    # ── Score banner ──────────────────────────────────────────────────────────
    color = "#dc3545" if score < 50 else "#fd7e14" if score < 70 else "#198754"
    grade = "Poor" if score < 50 else "Fair" if score < 70 else "Good" if score < 85 else "Excellent"

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                border-radius:16px;padding:2rem;margin-bottom:1.5rem;
                display:flex;align-items:center;gap:2rem">
        <div style="text-align:center;min-width:120px">
            <div style="font-size:3.5rem;font-weight:800;color:{color};line-height:1">{score}</div>
            <div style="color:#aaa;font-size:0.85rem">out of 100</div>
            <div style="color:{color};font-weight:600;margin-top:4px">{grade}</div>
        </div>
        <div style="flex:1">
            <div style="color:white;font-size:1.3rem;font-weight:600;margin-bottom:0.5rem">
                {len(issues)} issues found across {st.session_state.df_raw.shape[1]} columns
            </div>
            <div style="background:#ffffff22;border-radius:8px;height:12px;overflow:hidden">
                <div style="background:{color};width:{score}%;height:100%;border-radius:8px;
                            transition:width 0.5s ease"></div>
            </div>
            <div style="color:#ccc;font-size:0.8rem;margin-top:0.5rem">
                Dataset: {st.session_state.dataset_name} &nbsp;·&nbsp;
                {st.session_state.df_raw.shape[0]:,} rows &nbsp;·&nbsp;
                {st.session_state.df_raw.shape[1]} columns
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Severity pills ────────────────────────────────────────────────────────
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for iss in issues:
        counts[iss["severity"]] += 1

    pill_colors = {"critical":"#dc3545","high":"#fd7e14","medium":"#e6a817","low":"#0d6efd"}
    cols = st.columns(4)
    labels = [("🔴 Critical","critical"), ("🟠 High","high"), ("🟡 Medium","medium"), ("🔵 Low","low")]
    for col, (label, sev) in zip(cols, labels):
        c = pill_colors[sev]
        col.markdown(f"""
        <div style="background:{c}15;border:1.5px solid {c};border-radius:12px;
                    padding:0.8rem;text-align:center">
            <div style="font-size:1.6rem;font-weight:800;color:{c}">{counts[sev]}</div>
            <div style="font-size:0.8rem;color:{c};font-weight:600">{label}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Issue cards ───────────────────────────────────────────────────────────
    st.markdown("### Issues Found")
    st.caption("Click **Start Fixing** below to step through each issue. Completed steps are shown first.")

    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_issues = sorted(issues, key=lambda x: sev_order.get(x["severity"], 9))

    for iss in sorted_issues:
        sev   = iss["severity"]
        color = pill_colors[sev]
        bg    = SEVERITY_BG[sev]
        emoji = SEVERITY_EMOJI[sev]

        st.markdown(f"""
        <div style="background:{bg};border-left:4px solid {color};border-radius:0 10px 10px 0;
                    padding:0.9rem 1.1rem;margin-bottom:0.6rem">
            <div style="display:flex;justify-content:space-between;align-items:flex-start">
                <div>
                    <span style="background:{color};color:white;font-size:0.7rem;font-weight:700;
                                 padding:2px 8px;border-radius:10px;margin-right:8px">
                        {emoji} {sev.upper()}
                    </span>
                    <span style="font-weight:600;font-size:0.95rem">{iss['title']}</span>
                </div>
                <code style="font-size:0.78rem;background:#0001;padding:2px 8px;border-radius:6px">
                    {iss['column']}
                </code>
            </div>
            <div style="color:#555;font-size:0.85rem;margin-top:0.4rem;padding-left:4px">
                {iss['detected']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    if st.button("🛠️ Start Fixing Issues", type="primary", use_container_width=True):
        st.session_state.current_issue_idx = 0
        st.session_state.phase = "fixing"
        st.rerun()
