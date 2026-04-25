"""
Generates a clean audit PDF report using fpdf2.
"""

from fpdf import FPDF
from datetime import datetime
import pandas as pd


SEVERITY_COLORS = {
    "critical": (220, 53, 69),
    "high": (253, 126, 20),
    "medium": (255, 193, 7),
    "low": (13, 110, 253),
}

DECISION_LABELS = {
    "apply": "✓ Applied",
    "skip": "✗ Skipped",
    "custom": "✎ Custom Fix",
}


class AuditReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 30, 30)
        self.cell(0, 10, "🩺 DataDoctor — Data Quality Audit Report", ln=True)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        self.ln(4)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"DataDoctor Audit Report — Page {self.page_no()}", align="C")


def generate_pdf(
    dataset_name: str,
    df_raw: pd.DataFrame,
    df_clean: pd.DataFrame,
    issues: list,
    score_before: int,
    score_after: int,
) -> bytes:

    pdf = AuditReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(10, 10, 10)

    # ── Summary section ───────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "Dataset Summary", ln=True)
    pdf.set_font("Helvetica", "", 10)

    rows = [
        ("Dataset", dataset_name),
        ("Original Shape", f"{df_raw.shape[0]:,} rows × {df_raw.shape[1]} columns"),
        ("Cleaned Shape", f"{df_clean.shape[0]:,} rows × {df_clean.shape[1]} columns"),
        ("Health Score Before", f"{score_before}/100"),
        ("Health Score After", f"{score_after}/100"),
        ("Total Issues Found", str(len(issues))),
        ("Issues Applied", str(sum(1 for i in issues if i.get("decision") == "apply"))),
        ("Issues Skipped", str(sum(1 for i in issues if i.get("decision") == "skip"))),
        ("Custom Fixes", str(sum(1 for i in issues if i.get("decision") == "custom"))),
    ]

    for label, value in rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(60, 7, label + ":", border=0)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, value, ln=True)

    pdf.ln(4)

    # ── Issues breakdown ──────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Issues Detail", ln=True)
    pdf.ln(2)

    for iss in issues:
        sev = iss["severity"]
        color = SEVERITY_COLORS.get(sev, (100, 100, 100))
        decision = iss.get("decision") or "pending"
        decision_label = DECISION_LABELS.get(decision, decision)

        # Issue header bar
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(
            0, 7,
            f"  #{iss['id']}  {iss['title']}  |  {sev.upper()}  |  Column: {iss['column']}  |  {decision_label}",
            ln=True, fill=True
        )

        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Helvetica", "", 9)

        def safe_cell(label, text):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(35, 6, label, border=0)
            pdf.set_font("Helvetica", "", 9)
            # multi_cell for long text
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.multi_cell(0, 6, str(text)[:300])

        safe_cell("Detected:", iss.get("detected", ""))
        safe_cell("Recommended:", iss.get("recommended_fix", ""))

        if iss.get("ai_explanation"):
            safe_cell("AI Insight:", iss["ai_explanation"])
        if iss.get("ai_risk"):
            safe_cell("Risk:", iss["ai_risk"])
        if iss.get("custom_value"):
            safe_cell("Custom Fix:", iss["custom_value"])

        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 5, f"  AI Confidence: {iss.get('ai_confidence', 'N/A')}", ln=True)
        pdf.set_text_color(40, 40, 40)
        pdf.ln(3)

    return bytes(pdf.output())
