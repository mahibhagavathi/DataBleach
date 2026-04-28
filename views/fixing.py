import streamlit as st
import pandas as pd
import numpy as np
from utils.fixer import apply_fix
from utils.detector import compute_health_score

SEVERITY_COLORS = {"critical":"#dc3545","high":"#fd7e14","medium":"#e6a817","low":"#0d6efd"}
SEVERITY_EMOJI  = {"critical":"🔴","high":"🟠","medium":"🟡","low":"🔵"}


# ── Fix option builder ────────────────────────────────────────────────────────
def _get_fix_options(iss: dict, df: pd.DataFrame) -> list[dict]:
    """
    Returns a list of {label, description, action} dicts tailored to the issue.
    action is stored and used by fixer.py via issue['selected_fix_action'].
    """
    title = iss["title"]
    col   = iss["column"]
    opts  = []

    if title == "Exact Duplicate Rows":
        opts = [
            {"label": "Drop duplicates, keep first",   "action": "drop_dupes_keep_first"},
            {"label": "Drop duplicates, keep last",    "action": "drop_dupes_keep_last"},
            {"label": "Flag duplicates (add column)",  "action": "flag_dupes"},
        ]

    elif title == "Primary Key Violations":
        opts = [
            {"label": "Keep first occurrence",  "action": "pk_keep_first"},
            {"label": "Keep last occurrence",   "action": "pk_keep_last"},
            {"label": "Flag violations only",   "action": "pk_flag"},
        ]

    elif title in ("Completely Empty Column", "Constant Column", "Near-Constant Column",
                   "Accidental Index Column Export", "Unnamed Columns (Likely Index Export)"):
        opts = [
            {"label": "Drop the column",        "action": "drop_col"},
            {"label": "Keep it (skip)",         "action": "skip_builtin"},
        ]

    elif title == "High Null Rate":
        if col in df.columns:
            if pd.api.types.is_numeric_dtype(pd.to_numeric(df[col], errors="coerce")):
                med = round(pd.to_numeric(df[col], errors="coerce").median(), 2)
                mn  = round(pd.to_numeric(df[col], errors="coerce").mean(), 2)
                opts = [
                    {"label": f"Fill with median ({med})",   "action": "fill_median"},
                    {"label": f"Fill with mean ({mn})",      "action": "fill_mean"},
                    {"label": "Fill with 0",                  "action": "fill_zero"},
                    {"label": "Drop rows with null",          "action": "drop_null_rows"},
                ]
            else:
                try:
                    mode_val = df[col].dropna().mode().iloc[0]
                except Exception:
                    mode_val = "Unknown"
                opts = [
                    {"label": f"Fill with mode ('{mode_val}')", "action": "fill_mode"},
                    {"label": "Fill with 'Unknown'",             "action": "fill_unknown"},
                    {"label": "Drop rows with null",             "action": "drop_null_rows"},
                ]

    elif title == "Negative Values in Non-Negative Column":
        opts = [
            {"label": "Replace negatives with NaN",          "action": "neg_to_nan"},
            {"label": "Replace negatives with absolute value","action": "neg_to_abs"},
            {"label": "Drop rows with negative values",       "action": "neg_drop_rows"},
        ]

    elif title in ("Extreme / Impossible Values", "Impossible / Out-of-Range Values"):
        opts = [
            {"label": "Cap — clamp the value to the nearest valid boundary (e.g. age 999 → 110)",
             "action": "cap_percentile"},
            {"label": "Replace with blank — mark the bad value as missing (NaN) so it can be imputed later",
             "action": "extreme_to_nan"},
            {"label": "Drop rows — delete the entire row containing the bad value",
             "action": "extreme_drop_rows"},
        ]

    elif title == "Inconsistent Category Casing":
        opts = [
            {"label": "Standardize to Title Case",   "action": "title_case"},
            {"label": "Standardize to lowercase",    "action": "lower_case"},
            {"label": "Standardize to UPPERCASE",    "action": "upper_case"},
        ]

    elif title == "Leading / Trailing Whitespace":
        opts = [
            {"label": "Strip all whitespace",        "action": "strip_whitespace"},
        ]

    elif title == "Mixed Date Formats":
        opts = [
            {"label": "Standardize to YYYY-MM-DD",   "action": "date_iso"},
            {"label": "Standardize to DD/MM/YYYY",   "action": "date_dmy"},
        ]

    elif title == "Boolean Value Inconsistency":
        opts = [
            {"label": "Standardize to True/False",   "action": "bool_tf"},
            {"label": "Standardize to 1/0",          "action": "bool_10"},
            {"label": "Standardize to Yes/No",       "action": "bool_yesno"},
        ]

    elif title == "String Null Tokens in Column":
        opts = [
            {"label": "Replace tokens with NaN",     "action": "null_tokens_to_nan"},
        ]

    elif title == "Invalid Email Addresses":
        opts = [
            {"label": "Replace invalid emails with NaN",     "action": "invalid_email_nan"},
            {"label": "Drop rows with invalid emails",        "action": "invalid_email_drop"},
        ]

    elif title == "Inconsistent Phone Number Formats":
        opts = [
            {"label": "Standardize to digits only",          "action": "phone_digits"},
            {"label": "Flag invalid phones (add column)",     "action": "phone_flag"},
        ]

    elif title == "Column Names with Special Characters / Spaces":
        opts = [
            {"label": "Rename to snake_case",        "action": "rename_snake"},
        ]

    elif title == "Inconsistent Column Name Casing":
        opts = [
            {"label": "Lowercase all column names",  "action": "col_lower"},
            {"label": "snake_case all column names", "action": "col_snake"},
        ]

    elif title == "Numeric Column Stored as String":
        opts = [
            {"label": "Cast to float",               "action": "cast_float"},
            {"label": "Cast to integer",             "action": "cast_int"},
        ]

    elif title in ("Possibly Redundant Columns", "Redundant Date Component Column"):
        opts = [
            {"label": "Drop the redundant column",   "action": "drop_col"},
            {"label": "Keep both (skip)",            "action": "skip_builtin"},
        ]

    # Default fallback
    if not opts:
        opts = [
            {"label": "Apply recommended fix",       "action": "default"},
        ]

    return opts


def show_fixing():
    issues = st.session_state.issues
    idx    = st.session_state.current_issue_idx

    if idx >= len(issues):
        st.session_state.health_score_after = compute_health_score(
            [i for i in issues if i.get("decision") == "skip"]
        )
        st.session_state.phase = "results"
        st.rerun()
        return

    iss   = issues[idx]
    total = len(issues)

    # ── Header ────────────────────────────────────────────────────────────────
    st.title("🛠️ Fix Issues")

    prog_col, count_col = st.columns([4, 1])
    with prog_col:
        st.progress(idx / total)
    with count_col:
        reviewed = sum(1 for i in issues if i.get("decision"))
        st.markdown(f"**{reviewed}/{total}** reviewed")

    # ── Jump nav ──────────────────────────────────────────────────────────────
    with st.expander("⬇️ Jump to issue"):
        labels = [f"#{i['id']} [{i['severity'].upper()}] {i['title']} — {i['column']}" for i in issues]
        jump = st.selectbox("", labels, index=idx, label_visibility="collapsed")
        if st.button("Go", key="jump_btn"):
            st.session_state.current_issue_idx = labels.index(jump)
            st.rerun()

    st.divider()

    # ── Issue card ────────────────────────────────────────────────────────────
    sev   = iss["severity"]
    color = SEVERITY_COLORS.get(sev, "#333")
    emoji = SEVERITY_EMOJI.get(sev, "")

    st.markdown(f"""
    <div style="background:{'#fff5f5' if sev=='critical' else '#fff8f0' if sev=='high' else '#fffdf0' if sev=='medium' else '#f0f4ff'};
                border-left:5px solid {color};border-radius:0 12px 12px 0;
                padding:1rem 1.2rem;margin-bottom:1.2rem">
        <div style="font-size:0.75rem;font-weight:700;color:{color};letter-spacing:1px">
            {emoji} {sev.upper()} · ISSUE {idx+1} OF {total}
        </div>
        <div style="font-size:1.2rem;font-weight:700;margin:4px 0">{iss['title']}</div>
        <div style="font-size:0.85rem;color:#666">
            Column: <code style="background:#0001;padding:1px 6px;border-radius:4px">{iss['column']}</code>
        </div>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([3, 2])

    with left:
        st.markdown("**🔍 What was detected**")
        st.info(iss["detected"])

        ai_exp = iss.get("ai_explanation") or iss["detected"]
        if ai_exp and ai_exp != iss["detected"]:
            st.markdown("**🤖 AI Explanation**")
            st.write(ai_exp)

        st.markdown("**⚠️ Risk if Ignored**")
        st.warning(iss.get("ai_risk") or "May cause errors in downstream analysis.")

    with right:
        st.markdown("**📊 Before / After Preview**")
        df_raw = st.session_state.df_raw
        col_name = iss["column"]

        if col_name not in ("ALL", "Multiple") and col_name in df_raw.columns:
            try:
                sample_df = df_raw[[col_name]].copy()
                after_df  = apply_fix(sample_df.copy(), {**iss, "selected_fix_action": "default"})

                if col_name in after_df.columns:
                    before_vals = sample_df[col_name].astype(str).tolist()
                    after_vals  = after_df[col_name].astype(str).tolist()
                else:
                    before_vals = sample_df[col_name].astype(str).tolist()
                    after_vals  = ["(removed)"] * len(before_vals)

                changed = [(b, a) for b, a in zip(before_vals, after_vals) if b != a]
                if changed:
                    show = changed[:7]
                    st.caption(f"{len(changed)} rows will change — showing first {len(show)}:")
                    preview = pd.DataFrame(show, columns=["Before ❌", "After ✅"])
                    st.dataframe(preview, use_container_width=True, hide_index=True)
                else:
                    # Show nulls or interesting rows
                    null_rows = sample_df[sample_df[col_name].isna()]
                    interesting = null_rows.head(5) if len(null_rows) > 0 else sample_df.head(5)
                    st.caption("Sample values in this column:")
                    st.dataframe(
                        interesting[[col_name]].rename(columns={col_name: "Current Value"}),
                        use_container_width=True, hide_index=True
                    )
            except Exception:
                st.caption("Preview not available for this fix type.")
        else:
            # For ALL-column fixes, show row count impact
            try:
                after_df = apply_fix(df_raw.copy(), iss)
                rows_removed = len(df_raw) - len(after_df)
                cols_removed = df_raw.shape[1] - after_df.shape[1]
                st.metric("Rows before", f"{len(df_raw):,}")
                st.metric("Rows after",  f"{len(after_df):,}", delta=f"{-rows_removed}" if rows_removed else "no change")
                if cols_removed:
                    st.metric("Columns removed", cols_removed)
            except Exception:
                st.caption("Whole-dataset fix — preview not available.")

    st.divider()

    # ── Fix options ───────────────────────────────────────────────────────────
    st.markdown("**🔧 How would you like to fix this?**")

    fix_options = _get_fix_options(iss, st.session_state.df_raw)
    option_labels = [o["label"] for o in fix_options] + ["✏️ Enter a custom fix", "❌ Skip this issue"]

    chosen = st.radio("", option_labels, key=f"fix_radio_{idx}", label_visibility="collapsed")

    if chosen == "✏️ Enter a custom fix":
        custom_val = st.text_input(
            "Describe your fix (e.g. 'Replace with 0', 'Drop the column'):",
            key=f"custom_text_{idx}"
        )
        if st.button("✅ Apply Custom Fix", disabled=not custom_val, use_container_width=True, type="primary"):
            _record("custom", idx, issues, custom_val=custom_val, action="default")

    elif chosen == "❌ Skip this issue":
        if st.button("⏭️ Skip", use_container_width=True):
            _record("skip", idx, issues)

    else:
        selected_opt = next(o for o in fix_options if o["label"] == chosen)
        if st.button(f"✅ Apply: {chosen}", use_container_width=True, type="primary"):
            _record("apply", idx, issues, action=selected_opt["action"])

    # ── Bottom nav ────────────────────────────────────────────────────────────
    st.markdown("---")
    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if idx > 0 and st.button("← Back", use_container_width=True):
            st.session_state.current_issue_idx = idx - 1
            st.rerun()
    with nav2:
        st.caption(f"Issue {idx+1} of {total}")
    with nav3:
        if idx < total - 1 and st.button("Next →", use_container_width=True):
            if not iss.get("decision"):
                _record("skip", idx, issues)
            else:
                st.session_state.current_issue_idx = idx + 1
                st.rerun()

    if reviewed > 0:
        st.markdown("---")
        if st.button("🏁 Finish & Get Results", use_container_width=True):
            for i in issues:
                if not i.get("decision"):
                    i["decision"] = "skip"
            st.session_state.issues = issues
            st.session_state.phase  = "results"
            st.rerun()


def _record(decision, idx, issues, custom_val=None, action="default"):
    issues[idx]["decision"]            = decision
    issues[idx]["selected_fix_action"] = action
    if custom_val:
        issues[idx]["custom_value"] = custom_val

    # Rebuild df_clean from scratch by replaying ALL applied fixes in order.
    # This guarantees no fix is ever lost due to Streamlit reruns.
    df = st.session_state.df_raw.copy()
    for iss in issues:
        if iss.get("decision") in ("apply", "custom"):
            df = apply_fix(df, iss)
    st.session_state.df_clean = df

    st.session_state.issues            = issues
    st.session_state.current_issue_idx = idx + 1
    st.rerun()
