from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
)

from analyze_workbook import analyze_workbook


BASE_DIR = Path(__file__).resolve().parent
INCOMING_DIR = BASE_DIR / "incoming"
REPORT_DIR = BASE_DIR / "reports"
CHART_DIR = REPORT_DIR / "charts"


def find_latest_workbook():
    files = sorted(INCOMING_DIR.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError("No .xlsx workbook found.")
    return files[-1]


def find_sheet(analysis, name):
    for sheet in analysis.get("sheets", []):
        if sheet.get("sheet") == name:
            return sheet
    return None


def make_financial_chart(analysis):
    sheet = find_sheet(analysis, "Financial_Summary")

    if not sheet:
        return None

    summary = sheet.get("numeric_summary", {})

    labels = []
    values = []

    for column in [
        "Gross Revenue",
        "Operating Expenses",
        "Net Profit (Calc)",
        "Reported Profit (Ledger)",
    ]:
        if column in summary:
            labels.append(column)
            values.append(summary[column]["sum"])

    if not values:
        return None

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    output = CHART_DIR / "financial_summary.png"

    plt.figure(figsize=(9, 5))
    plt.bar(labels, values)
    plt.title("Financial Summary")
    plt.ylabel("USD")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()

    return output


def make_regional_chart(analysis):
    sheet = find_sheet(analysis, "Monthly_Perf")

    if not sheet:
        return None

    summary = sheet.get("numeric_summary", {})

    regions = ["North", "South", "East", "West", "Central"]
    labels = []
    values = []

    for region in regions:
        if region in summary:
            labels.append(region)
            values.append(summary[region]["sum"])

    if not values:
        return None

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    output = CHART_DIR / "regional_performance.png"

    plt.figure(figsize=(9, 5))
    plt.bar(labels, values)
    plt.title("Regional Units Sold")
    plt.ylabel("Units")
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()

    return output


def add_page_number(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(
        A4[0] / 2,
        0.45 * inch,
        f"Page {document.page}",
    )
    canvas.restoreState()


def build_pdf(workbook, report_text, analysis):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    output = REPORT_DIR / f"{workbook.stem}_weekly_report.pdf"

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        spaceBefore=12,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        leading=15,
        spaceAfter=7,
    )

    story = []

    story.append(Paragraph(
        "Internal Data Analysis Report",
        title_style,
    ))

    story.append(Paragraph(
        f"<b>Workbook:</b> {workbook.name}",
        body_style,
    ))

    story.append(Spacer(1, 12))

    financial_chart = make_financial_chart(analysis)

    if financial_chart:
        story.append(Paragraph(
            "Financial Summary",
            heading_style,
        ))
        story.append(Image(
            str(financial_chart),
            width=6.8 * inch,
            height=3.8 * inch,
        ))
        story.append(Spacer(1, 10))

    regional_chart = make_regional_chart(analysis)

    if regional_chart:
        story.append(Paragraph(
            "Regional Performance",
            heading_style,
        ))
        story.append(Image(
            str(regional_chart),
            width=6.8 * inch,
            height=3.8 * inch,
        ))

    story.append(PageBreak())

    story.append(Paragraph(
        "Qwen Analysis",
        heading_style,
    ))

    for line in report_text.splitlines():
        line = line.strip()

        if not line:
            story.append(Spacer(1, 5))
            continue

        if line.startswith("###"):
            text = line.lstrip("#").strip()
            story.append(Paragraph(text, heading_style))
        elif line.startswith("**") and line.endswith("**"):
            text = line.strip("*")
            story.append(Paragraph(text, heading_style))
        elif line.startswith("- "):
            text = "• " + line[2:]
            story.append(Paragraph(text, body_style))
        else:
            story.append(Paragraph(line, body_style))

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    return output


def main():
    workbook = find_latest_workbook()

    report_file = REPORT_DIR / f"{workbook.stem}_weekly_report.txt"

    if not report_file.exists():
        raise FileNotFoundError(
            f"Qwen report not found: {report_file}"
        )

    print(f"Loading workbook: {workbook.name}")
    analysis = analyze_workbook(workbook)

    print(f"Loading Qwen report: {report_file.name}")
    report_text = report_file.read_text(encoding="utf-8")

    print("Generating charts and PDF...")
    output = build_pdf(
        workbook,
        report_text,
        analysis,
    )

    print()
    print("===== PDF REPORT =====")
    print(f"PDF created: {output}")
    print(f"Size: {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
