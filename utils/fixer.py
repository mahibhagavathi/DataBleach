"""
Applies approved fixes to the dataframe based on issue category and decision.
"""

import pandas as pd
import numpy as np
import re


EXCEL_ERRORS = {"#NULL!", "#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#NUM!", "#N/A"}
NULL_TOKENS = {"n/a", "na", "none", "null", "unknown", "-", "--", "?", "nil"}
CURRENCY_RE = re.compile(r"[\$€£¥,]")
COMMA_NUM_RE = re.compile(r"^\d{1,3}(,\d{3})+(\.\d+)?$")


def apply_fix(df: pd.DataFrame, issue: dict) -> pd.DataFrame:
    """
    Applies the fix for a single issue to df and returns the modified copy.
    """
    df = df.copy()
    col = issue["column"]
    category = issue["category"]
    title = issue["title"]
    custom = issue.get("custom_value", "").strip() if issue.get("custom_value") else ""

    try:
        # ── CRITICAL ──────────────────────────────────────────────────────────
        if title == "Exact Duplicate Rows":
            df = df.drop_duplicates(keep="first").reset_index(drop=True)

        elif title == "Primary Key Violations":
            df = df.drop_duplicates(subset=[col], keep="first").reset_index(drop=True)

        elif title == "Completely Empty Column":
            if col in df.columns:
                df = df.drop(columns=[col])

        elif title == "Completely Empty Rows":
            df = df.dropna(how="all").reset_index(drop=True)

        elif title == "Corrupted / Excel Error Values":
            if col in df.columns:
                df[col] = df[col].apply(lambda x: np.nan if str(x) in EXCEL_ERRORS else x)

        elif title == "Repeated Header Row Mid-File":
            if col in df.columns:
                df = df[df[col].astype(str).str.strip() != str(col).strip()].reset_index(drop=True)

        # ── HIGH ──────────────────────────────────────────────────────────────
        elif title == "High Null Rate":
            if col in df.columns:
                if custom:
                    df[col] = df[col].fillna(custom)
                elif pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].median())
                else:
                    mode = df[col].mode()
                    df[col] = df[col].fillna(mode[0] if len(mode) else "Unknown")

        elif title == "Numeric Column Stored as String":
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        elif title == "Negative Values in Non-Negative Column":
            if col in df.columns:
                df[col] = df[col].apply(lambda x: np.nan if pd.notna(x) and x < 0 else x)

        elif title == "Future Dates in Historical Column":
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors="coerce")
                parsed[parsed > pd.Timestamp.now()] = pd.NaT
                df[col] = parsed

        elif title == "Null Values in ID Column":
            df = df.dropna(subset=[col]).reset_index(drop=True)

        elif title == "String Null Tokens in Column":
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: np.nan if pd.notna(x) and str(x).strip().lower() in NULL_TOKENS else x
                )

        # ── MEDIUM ────────────────────────────────────────────────────────────
        elif title == "Inconsistent Category Casing":
            if col in df.columns:
                df[col] = df[col].str.strip().str.title()

        elif title == "Leading / Trailing Whitespace":
            if col in df.columns:
                df[col] = df[col].str.strip()

        elif title == "Currency Symbols in Numeric Column":
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(CURRENCY_RE, "", regex=True)
                df[col] = pd.to_numeric(df[col], errors="coerce")

        elif title == "Comma-Formatted Numbers as Strings":
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(",", "")
                df[col] = pd.to_numeric(df[col], errors="coerce")

        elif title == "Boolean Value Inconsistency":
            if col in df.columns:
                bool_map = {
                    "true": True, "yes": True, "y": True, "1": True, "t": True,
                    "false": False, "no": False, "n": False, "0": False, "f": False,
                }
                df[col] = df[col].astype(str).str.lower().map(bool_map)

        elif title == "Mixed Date Formats":
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")

        elif title == "Leading Zeros Stripped from Postal Code":
            if col in df.columns:
                df[col] = df[col].astype(str).str.zfill(5)

        elif title == "Statistical Outliers (IQR)":
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 3 * iqr
                upper = q3 + 3 * iqr
                df[col] = df[col].clip(lower=lower, upper=upper)

        elif title == "Invalid Email Addresses":
            if col in df.columns:
                import re as re2
                email_re = re2.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
                df[col] = df[col].apply(
                    lambda x: x if pd.isna(x) or email_re.match(str(x)) else np.nan
                )

        # ── LOW ───────────────────────────────────────────────────────────────
        elif title in ("Unnamed Columns (Likely Index Export)", "Accidental Index Column Export"):
            cols_to_drop = [c for c in df.columns if str(c).startswith("Unnamed")]
            if not cols_to_drop and col in df.columns:
                cols_to_drop = [col]
            df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

        elif title == "Constant Column":
            if col in df.columns:
                df = df.drop(columns=[col])

        elif title in ("Near-Constant Column",):
            if col in df.columns:
                df = df.drop(columns=[col])

        elif title == "Column Names with Special Characters / Spaces":
            import re as re2
            df.columns = [re2.sub(r"[^a-zA-Z0-9]", "_", str(c)).lower().strip("_") for c in df.columns]

        elif title == "Inconsistent Column Name Casing":
            df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

        elif title == "Possibly Redundant Columns":
            # Drop the second column mentioned
            if "&" in str(col):
                parts = str(col).replace("[", "").replace("]", "").replace("'", "").split("&")
                to_drop = parts[-1].strip()
                if to_drop in df.columns:
                    df = df.drop(columns=[to_drop])

    except Exception as e:
        # If a fix fails, return df unchanged — never crash the app
        pass

    return df
