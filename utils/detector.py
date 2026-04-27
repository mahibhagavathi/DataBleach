"""
Detection engine — checks for all 50 data quality issue types.
Returns a list of issue dicts ready for the fix workflow.
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _issue(id_, severity, title, column, detected, recommended_fix, category):
    return {
        "id": id_,
        "severity": severity,       # critical / high / medium / low
        "title": title,
        "column": column,
        "detected": detected,       # human-readable description of what was found
        "recommended_fix": recommended_fix,
        "decision": None,           # apply / skip / custom
        "custom_value": None,
        "ai_explanation": None,
        "ai_risk": None,
        "ai_confidence": None,
        "category": category,
    }


EXCEL_ERRORS = {"#NULL!", "#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#NUM!", "#N/A"}

DATE_PATTERNS = [
    r"^\d{4}-\d{2}-\d{2}$",
    r"^\d{2}/\d{2}/\d{4}$",
    r"^\d{2}-\d{2}-\d{4}$",
    r"^\w+ \d{1,2},\s*\d{4}$",
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_FORMATS = [
    re.compile(r"^\(\d{3}\)\s\d{3}-\d{4}$"),
    re.compile(r"^\d{3}-\d{3}-\d{4}$"),
    re.compile(r"^\+\d{10,15}$"),
    re.compile(r"^\d{10}$"),
]
CURRENCY_RE = re.compile(r"[\$€£¥]")
COMMA_NUM_RE = re.compile(r"^\d{1,3}(,\d{3})+(\.\d+)?$")


def _is_numeric_col(series: pd.Series) -> bool:
    try:
        pd.to_numeric(series.dropna(), errors="raise")
        return True
    except Exception:
        return False


def _detect_date_format(val: str):
    for p in DATE_PATTERNS:
        if re.match(p, str(val).strip()):
            return p
    return None


# ── Master detection function ─────────────────────────────────────────────────

def detect_issues(df: pd.DataFrame) -> list:
    issues = []
    iid = [1]

    def add(severity, title, column, detected, fix, category):
        issues.append(_issue(iid[0], severity, title, column, detected, fix, category))
        iid[0] += 1

    # ── 🔴 CRITICAL ──────────────────────────────────────────────────────────

    # 1. Exact duplicate rows
    n_dupes = df.duplicated().sum()
    if n_dupes > 0:
        add("critical", "Exact Duplicate Rows", "ALL",
            f"{n_dupes} fully duplicate rows found.",
            f"Drop {n_dupes} duplicate rows, keep first occurrence.",
            "duplicates")

    # 2. Primary key violations (columns that look like IDs)
    for col in df.columns:
        if any(k in col.lower() for k in ["id", "key", "code"]):
            vc = df[col].dropna().value_counts()
            violations = (vc > 1).sum()
            if violations > 0:
                add("critical", "Primary Key Violations", col,
                    f"{violations} duplicate values found in `{col}` — expected unique.",
                    "Investigate duplicates; keep most recent or merge records.",
                    "integrity")

    # 3. Completely empty columns
    for col in df.columns:
        if df[col].isna().all():
            add("critical", "Completely Empty Column", col,
                f"Column `{col}` is 100% null — contains no data.",
                f"Drop column `{col}` — it adds no information.",
                "nulls")

    # 4. Completely empty rows
    empty_rows = df.isnull().all(axis=1).sum()
    if empty_rows > 0:
        add("critical", "Completely Empty Rows", "ALL",
            f"{empty_rows} rows with no values at all.",
            f"Drop {empty_rows} fully empty rows.",
            "nulls")

    # 5. Corrupted / Excel error values
    for col in df.columns:
        if df[col].dtype == object:
            mask = df[col].astype(str).isin(EXCEL_ERRORS)
            if mask.any():
                vals = df.loc[mask, col].unique().tolist()
                add("critical", "Corrupted / Excel Error Values", col,
                    f"Found Excel error tokens: {vals}",
                    "Replace error tokens with NaN, then handle as missing values.",
                    "corruption")

    # 6. Header row missing (first row looks like data, not headers)
    if all(str(c).startswith("Unnamed") or str(c).isdigit() for c in df.columns):
        add("critical", "Header Row Possibly Missing", "ALL",
            "All column names are auto-generated — original headers may be missing.",
            "Reload CSV with the first data row promoted to headers.",
            "structure")

    # 7. Multiple / repeated header rows mid-file
    for col in df.columns:
        if df[col].dtype == object:
            matches = (df[col].astype(str).str.strip() == str(col).strip()).sum()
            if matches > 0:
                add("critical", "Repeated Header Row Mid-File", col,
                    f"Column name `{col}` appears {matches}x as a data value — headers duplicated mid-file.",
                    "Remove repeated header rows that appear as data rows.",
                    "structure")

    # 8. Mixed delimiters detected (hard to catch post-parse, flag as warning)
    for col in df.columns:
        if df[col].dtype == object:
            has_semi = df[col].astype(str).str.contains(";", na=False).sum()
            has_pipe = df[col].astype(str).str.contains(r"\|", na=False, regex=True).sum()
            if has_semi > len(df) * 0.3 or has_pipe > len(df) * 0.3:
                add("critical", "Possible Mixed Delimiters", col,
                    f"Many values in `{col}` contain `;` or `|` — file may have been parsed with wrong delimiter.",
                    "Re-parse the CSV specifying the correct delimiter (sep=';' or sep='|').",
                    "structure")

    # ── 🟠 HIGH ──────────────────────────────────────────────────────────────

    for col in df.columns:
        null_pct = df[col].isna().mean()

        # 9. Missing values above 20%
        if 0.20 <= null_pct < 1.0:
            add("high", "High Null Rate", col,
                f"{null_pct:.1%} of values are missing ({df[col].isna().sum():,} rows).",
                "Impute with median (numeric) or mode (categorical), or drop if >50% null.",
                "nulls")

        # 10. Wrong data types (numbers stored as strings)
        if df[col].dtype == object and _is_numeric_col(df[col]):
            add("high", "Numeric Column Stored as String", col,
                f"`{col}` contains numeric values but is typed as string/object.",
                f"Cast `{col}` to float64.",
                "dtypes")

    # 11. Impossible / out-of-range values
    for col in df.columns:
        numeric_col = pd.to_numeric(df[col], errors="coerce")
        if numeric_col.notna().sum() < 10:
            continue
        q1, q99 = numeric_col.quantile(0.01), numeric_col.quantile(0.99)
        iqr = numeric_col.quantile(0.75) - numeric_col.quantile(0.25)
        # Skip low-range columns like ratings/scores (range < 20) — not "impossible"
        col_range = numeric_col.max() - numeric_col.min()
        if col_range < 20 and numeric_col.max() <= 100:
            continue
        if q99 <= 0:
            continue
        extreme = ((numeric_col < q1 * 10) | (numeric_col > q99 * 10)) & numeric_col.notna()
        n_extreme = int(extreme.sum())
        if n_extreme > 0:
            add("high", "Extreme / Impossible Values", col,
                f"{n_extreme} values far outside expected range in `{col}`. Min: {numeric_col.min()}, Max: {numeric_col.max()}.",
                "Cap at 1st/99th percentile or investigate and remove if confirmed erroneous.",
                "outliers")

    # 12. Negative values in non-negative columns
    NON_NEG_KEYWORDS = [
        "price", "amount", "fare", "sales", "revenue", "cost", "age",
        "distance", "count", "qty", "quantity", "year", "income", "salary",
        "wage", "score", "rating", "duration", "hours", "days", "months",
        "experience", "tenure", "size", "weight", "height", "population",
        "beds", "physicians", "mortality", "expectancy", "rate", "percent",
    ]
    for col in df.columns:
        if not any(k in col.lower() for k in NON_NEG_KEYWORDS):
            continue
        numeric_vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(numeric_vals) == 0:
            continue
        n_neg = (numeric_vals < 0).sum()
        if n_neg > 0:
            neg_examples = numeric_vals[numeric_vals < 0].head(3).tolist()
            add("high", "Negative Values in Non-Negative Column", col,
                f"{n_neg} negative value(s) in `{col}` where only positive values make sense. Examples: {neg_examples}.",
                "Replace negatives with NaN and investigate source data.",
                "validity")

    # 13. Future dates in historical columns
    for col in df.columns:
        if any(k in col.lower() for k in ["date", "time", "created", "updated", "birth"]):
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                future = (parsed > pd.Timestamp.now()).sum()
                if future > 0:
                    add("high", "Future Dates in Historical Column", col,
                        f"{future} dates in `{col}` are in the future.",
                        "Replace future dates with NaT and investigate data entry errors.",
                        "validity")
            except Exception:
                pass

    # 14. Dates before plausible minimum
    for col in df.columns:
        if any(k in col.lower() for k in ["birth", "dob", "born"]):
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                old = (parsed < pd.Timestamp("1900-01-01")).sum()
                if old > 0:
                    add("high", "Implausibly Old Dates", col,
                        f"{old} birth dates before 1900 in `{col}`.",
                        "Replace with NaT — likely data entry errors.",
                        "validity")
            except Exception:
                pass

    # 15. ID columns with nulls
    for col in df.columns:
        if any(k in col.lower() for k in ["_id", "id_", " id", "id"]):
            n_null = df[col].isna().sum()
            if n_null > 0:
                add("high", "Null Values in ID Column", col,
                    f"`{col}` has {n_null} missing values — ID columns should never be null.",
                    "Investigate source; assign surrogate keys or drop affected rows.",
                    "integrity")

    # 16. All values identical in non-constant column
    for col in df.columns:
        if df[col].nunique(dropna=True) == 1 and not any(k in col.lower() for k in ["currency", "status", "flag", "type"]):
            add("high", "Suspicious Single-Value Column", col,
                f"All non-null values in `{col}` are identical: '{df[col].dropna().iloc[0] if len(df[col].dropna()) > 0 else 'N/A'}'.",
                "Verify this is expected; if not, may indicate a data pipeline error.",
                "validity")

    # 17. String tokens in numeric columns
    for col in df.columns:
        if df[col].dtype == object:
            null_like = df[col].astype(str).str.lower().isin(["n/a", "na", "none", "null", "unknown", "-", "--", "?", "nil"])
            n = null_like.sum()
            if n > 0:
                add("high", "String Null Tokens in Column", col,
                    f"{n} values in `{col}` are text placeholders for missing data (e.g. 'N/A', 'unknown', '-').",
                    "Replace text null tokens with actual NaN.",
                    "nulls")

    # ── 🟡 MEDIUM ─────────────────────────────────────────────────────────────

    for col in df.columns:
        if df[col].dtype == object:

            # 18. Inconsistent categories
            uniq = df[col].dropna().unique()
            lower_map = {}
            for v in uniq:
                lower_map.setdefault(str(v).strip().lower(), []).append(v)
            conflicts = {k: v for k, v in lower_map.items() if len(v) > 1}
            if conflicts:
                example = list(conflicts.values())[0]
                add("medium", "Inconsistent Category Casing", col,
                    f"Same category written multiple ways in `{col}` e.g. {example}.",
                    f"Standardize all values in `{col}` to title case.",
                    "consistency")

            # 19. Whitespace / trailing spaces
            has_space = df[col].str.contains(r"^\s|\s$", na=False, regex=True).sum()
            if has_space > 0:
                add("medium", "Leading / Trailing Whitespace", col,
                    f"{has_space} values in `{col}` have leading or trailing spaces.",
                    "Strip whitespace from all string values.",
                    "formatting")

            # 20. Currency symbols in numeric column
            has_currency = df[col].str.contains(CURRENCY_RE, na=False).sum()
            if has_currency > 5:
                add("medium", "Currency Symbols in Numeric Column", col,
                    f"{has_currency} values in `{col}` contain currency symbols (£, $, €).",
                    "Strip symbols and cast to float.",
                    "formatting")

            # 21. Comma-formatted numbers as strings
            has_comma_num = df[col].apply(lambda x: bool(COMMA_NUM_RE.match(str(x))) if pd.notna(x) else False).sum()
            if has_comma_num > 5:
                add("medium", "Comma-Formatted Numbers as Strings", col,
                    f"{has_comma_num} values like '1,234,567' in `{col}` — stored as string, not numeric.",
                    "Remove commas and cast to float.",
                    "formatting")

            # 22. Boolean inconsistency
            bool_variants = {"true", "false", "yes", "no", "y", "n", "1", "0", "t", "f"}
            col_lower = set(df[col].dropna().astype(str).str.lower().unique())
            overlap = col_lower & bool_variants
            if len(overlap) > 2:
                add("medium", "Boolean Value Inconsistency", col,
                    f"`{col}` has mixed boolean representations: {list(overlap)}.",
                    "Standardize to True/False or 1/0.",
                    "consistency")

            # 23. Inconsistent country/state names
            if any(k in col.lower() for k in ["country", "nation", "state", "region"]):
                if df[col].nunique() > 1:
                    short_long = df[col].dropna().astype(str)
                    has_abbrev = short_long.str.len().between(2, 3).sum()
                    has_long = (short_long.str.len() > 6).sum()
                    if has_abbrev > 0 and has_long > 0:
                        add("medium", "Inconsistent Geographic Name Formats", col,
                            f"`{col}` mixes abbreviations (e.g. 'US') with full names (e.g. 'United States').",
                            "Standardize to full country/region names using a lookup table.",
                            "consistency")

            # 24. Phone format inconsistency
            if any(k in col.lower() for k in ["phone", "mobile", "tel", "contact"]):
                formats_found = set()
                for v in df[col].dropna().astype(str):
                    matched = False
                    for fmt in PHONE_FORMATS:
                        if fmt.match(v.strip()):
                            formats_found.add(fmt.pattern)
                            matched = True
                            break
                    if not matched:
                        formats_found.add("unknown")
                if len(formats_found) > 1:
                    add("medium", "Inconsistent Phone Number Formats", col,
                        f"`{col}` has phone numbers in {len(formats_found)} different formats.",
                        "Standardize to E.164 format: +[country][number].",
                        "formatting")

            # 25. Invalid email addresses
            if any(k in col.lower() for k in ["email", "mail", "e-mail"]):
                invalid = df[col].dropna().astype(str).apply(lambda x: not EMAIL_RE.match(x)).sum()
                if invalid > 0:
                    add("medium", "Invalid Email Addresses", col,
                        f"{invalid} values in `{col}` don't match valid email format.",
                        "Flag invalid emails as NaN or correct at source.",
                        "validity")

            # 26. Free text in categorical column
            if df[col].nunique() / max(len(df[col].dropna()), 1) < 0.1:
                long_vals = df[col].dropna().astype(str).str.len()
                if long_vals.max() > 50:
                    add("medium", "Free Text in Categorical Column", col,
                        f"`{col}` looks categorical but contains very long values (max {long_vals.max()} chars).",
                        "Review long entries and normalize or move to a separate notes field.",
                        "consistency")

    # 27. Mixed date formats
    for col in df.columns:
        if any(k in col.lower() for k in ["date", "time", "day", "month", "year"]):
            if df[col].dtype == object:
                formats_seen = set()
                for v in df[col].dropna().astype(str)[:100]:
                    fmt = _detect_date_format(v)
                    formats_seen.add(fmt if fmt else "unknown")
                if len(formats_seen) > 1:
                    add("medium", "Mixed Date Formats", col,
                        f"`{col}` has dates in {len(formats_seen)} different formats.",
                        "Parse all dates and standardize to ISO format YYYY-MM-DD.",
                        "formatting")

    # 28. Leading zeros stripped (zip codes etc)
    for col in df.columns:
        if any(k in col.lower() for k in ["zip", "postal", "pincode", "postcode"]):
            if df[col].dtype in [np.int64, int]:
                short = (df[col].astype(str).str.len() < 5).sum()
                if short > 0:
                    add("medium", "Leading Zeros Stripped from Postal Code", col,
                        f"{short} postal codes in `{col}` are shorter than 5 digits — leading zeros likely stripped.",
                        "Cast to string and zero-pad to expected length.",
                        "formatting")

    # 29. Inconsistent units
    for col in df.columns:
        if any(k in col.lower() for k in ["weight", "height", "distance", "size"]):
            if df[col].dtype in [np.float64, np.int64, float, int]:
                q25, q75 = df[col].quantile(0.25), df[col].quantile(0.75)
                if q75 > 0 and q25 > 0 and q75 / q25 > 50:
                    add("medium", "Possible Mixed Units", col,
                        f"`{col}` has very high variance (25th pct: {q25:.1f}, 75th pct: {q75:.1f}) — possible unit mismatch (e.g. kg vs lbs).",
                        "Verify units with data source; convert all values to one unit.",
                        "validity")

    # 30. Outliers (IQR method)
    for col in df.columns:
        if df[col].dtype in [np.float64, np.int64, float, int]:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 3 * iqr
                upper = q3 + 3 * iqr
                n_out = ((df[col] < lower) | (df[col] > upper)).sum()
                if n_out > 0:
                    add("medium", "Statistical Outliers (IQR)", col,
                        f"{n_out} outliers detected in `{col}` using IQR method (beyond 3×IQR).",
                        "Investigate each outlier; cap, remove, or keep based on business context.",
                        "outliers")

    # 31. Fuzzy / near-duplicate rows (sample-based for performance)
    try:
        from rapidfuzz import fuzz
        str_cols = df.select_dtypes(include="object").columns.tolist()
        if str_cols:
            sample = df[str_cols].fillna("").astype(str).apply(lambda r: " ".join(r), axis=1).head(200)
            fuzzy_dupes = 0
            seen = []
            for val in sample:
                for s in seen:
                    if fuzz.ratio(val, s) > 90 and val != s:
                        fuzzy_dupes += 1
                        break
                seen.append(val)
            if fuzzy_dupes > 0:
                add("medium", "Fuzzy / Near-Duplicate Rows", "Multiple",
                    f"~{fuzzy_dupes} rows appear to be near-duplicates (>90% similar text).",
                    "Review near-duplicates manually and merge or remove as appropriate.",
                    "duplicates")
    except ImportError:
        pass

    # ── 🔵 LOW ────────────────────────────────────────────────────────────────

    # 32. Low variance columns
    for col in df.columns:
        if df[col].dtype == object:
            top_freq = df[col].value_counts(normalize=True).iloc[0] if df[col].notna().any() else 0
            if top_freq > 0.99:
                add("low", "Near-Constant Column", col,
                    f"`{col}` is {top_freq:.1%} the same value — very low variance.",
                    "Consider dropping this column if it adds no analytical value.",
                    "redundancy")

    # 33. Near-100% unique columns (likely IDs mislabeled)
    for col in df.columns:
        if df[col].dtype == object:
            uniq_ratio = df[col].nunique() / max(len(df[col].dropna()), 1)
            if uniq_ratio > 0.95 and not any(k in col.lower() for k in ["id", "key", "uuid", "name", "email"]):
                add("low", "Suspiciously High Cardinality", col,
                    f"`{col}` is {uniq_ratio:.0%} unique — may be a mislabeled ID or free-text column.",
                    "Verify if this should be a categorical column or identifier.",
                    "structure")

    # 34. Unnamed columns
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed")]
    if unnamed:
        add("low", "Unnamed Columns (Likely Index Export)", str(unnamed),
            f"{len(unnamed)} unnamed column(s) found: {unnamed}. Likely a Pandas index accidentally exported.",
            "Drop unnamed columns.",
            "structure")

    # 35. Redundant columns
    str_cols = df.select_dtypes(include="object").columns.tolist()
    for i, c1 in enumerate(str_cols):
        for c2 in str_cols[i+1:]:
            if df[c1].dtype == df[c2].dtype:
                try:
                    same = (df[c1].fillna("__NA__") == df[c2].fillna("__NA__")).mean()
                    if same > 0.95:
                        add("low", "Possibly Redundant Columns", f"{c1} & {c2}",
                            f"`{c1}` and `{c2}` are {same:.0%} identical — may be duplicates.",
                            f"Drop one of `{c1}` or `{c2}` if they carry the same information.",
                            "redundancy")
                except Exception:
                    pass

    # 36. Constant columns
    for col in df.columns:
        if df[col].nunique(dropna=True) == 1:
            add("low", "Constant Column", col,
                f"`{col}` has only one unique value across all rows.",
                f"Drop `{col}` — it contains no variation and cannot be used for analysis.",
                "redundancy")

    # 37. Index column accidentally exported
    for col in df.columns:
        s = df[col].dropna()
        if len(s) > 10 and pd.api.types.is_integer_dtype(s):
            is_seq = (s.reset_index(drop=True) == pd.RangeIndex(len(s))).mean()
            if is_seq > 0.98:
                add("low", "Accidental Index Column Export", col,
                    f"`{col}` looks like a row index (sequential integers 0, 1, 2...) accidentally exported.",
                    f"Drop `{col}`.",
                    "structure")

    # 38. Column names with special characters
    bad_name_cols = [c for c in df.columns if re.search(r"[^a-zA-Z0-9_]", str(c))]
    if bad_name_cols:
        add("low", "Column Names with Special Characters / Spaces", str(bad_name_cols),
            f"{len(bad_name_cols)} column(s) have spaces or special characters: {bad_name_cols}.",
            "Rename columns to snake_case (lowercase, underscores only).",
            "naming")

    # 39. Inconsistent column name casing
    casings = set(
        "upper" if str(c).isupper() else "lower" if str(c).islower() else "mixed"
        for c in df.columns
    )
    if len(casings) > 1:
        add("low", "Inconsistent Column Name Casing", "ALL",
            f"Column names use mixed casing styles: {casings}.",
            "Standardize all column names to snake_case.",
            "naming")

    # 40. Duplicate column names
    if len(df.columns) != len(set(df.columns)):
        from collections import Counter
        duped = [k for k, v in Counter(df.columns).items() if v > 1]
        add("low", "Duplicate Column Names", str(duped),
            f"Duplicate column names detected: {duped}. Second occurrence silently dropped by Pandas.",
            "Rename or drop duplicate columns before analysis.",
            "structure")

    # 41. Columns that are subsets of other columns
    for col in df.columns:
        if any(k in col.lower() for k in ["year", "month", "day"]):
            date_cols = [c for c in df.columns if "date" in c.lower()]
            if date_cols:
                add("low", "Redundant Date Component Column", col,
                    f"`{col}` may be derivable from `{date_cols[0]}` — storing both is redundant.",
                    f"Consider dropping `{col}` and deriving it from `{date_cols[0]}` when needed.",
                    "redundancy")
                break  # one warning is enough

    # 42. Columns with high null rate (not yet flagged as critical/high)
    for col in df.columns:
        null_pct = df[col].isna().mean()
        if 0.80 <= null_pct < 1.0:
            if not any(i["column"] == col and i["severity"] in ("critical", "high") for i in issues):
                add("low", "Very High Null Rate Column", col,
                    f"`{col}` is {null_pct:.0%} null — may not be worth keeping.",
                    "Consider dropping this column or flagging for data collection improvement.",
                    "nulls")

    return issues


# ── Health score ──────────────────────────────────────────────────────────────

def compute_health_score(issues: list) -> int:
    weights = {"critical": 15, "high": 8, "medium": 4, "low": 1}
    penalty = sum(weights.get(i["severity"], 0) for i in issues)
    score = max(0, 100 - penalty)
    return score
