"""Read-only structural audit for an insurance financial report."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from insurance_statement_parser import (
    parse_cash_flow,
    parse_financial_position,
    parse_profit_or_loss,
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PDF = (
    BASE_DIR
    / "reports"
    / "research"
    / "source_docs"
    / "nepal_life_q1_financial_report.pdf"
)
DEFAULT_OUTPUT = (
    BASE_DIR
    / "reports"
    / "research"
    / "source_docs"
    / "nepal_life_q1_financial_report_audit.json"
)

EXPECTED_COLUMNS = {
    "Condensed Consolidated Statement of Financial Position": 4,
    "Condensed Consolidated Statement of Profit or Loss": 8,
    "Consolidated Statement of Cash Flows": 4,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(line: str) -> str:
    return " ".join(line.split()).strip()


def find_incomplete_metric_rows(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find recognized metric rows that lack expected entity/period values."""
    metric_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)

    for record in records:
        group_key = (
            record.get("statement"),
            record.get("section"),
            record.get("metric"),
            record.get("source_page"),
        )
        metric_groups[group_key].append(record)

    incomplete_rows = []
    for key, group in metric_groups.items():
        expected = EXPECTED_COLUMNS.get(key[0])
        if expected is not None and len(group) != expected:
            incomplete_rows.append({
                "key": list(key),
                "expected_values": expected,
                "actual_values": len(group),
                "source_texts": [item.get("source_text") for item in group],
            })

    return incomplete_rows


def audit_report(pdf_path: Path) -> dict[str, Any]:
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported.")

    pages: list[list[str]] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append([normalized(line) for line in text.splitlines()
                      if line.strip()])

    records: list[dict[str, Any]] = []

    # These statement parsers require a complete statement on the supplied
    # page. The source page is retained on every parsed record.
    for page_number, lines in enumerate(pages, start=1):
        records.extend(parse_financial_position(lines, page_number))
        records.extend(parse_profit_or_loss(lines, page_number))

    # Limit cash-flow parsing to the actual cash-flow statement, retaining
    # page-aware lines because the statement continues across pages.
    cash_flow_lines: list[tuple[int, str]] = []
    in_cash_flow = False
    found_cash_flow_end = False

    for page_number, lines in enumerate(pages, start=1):
        for line in lines:
            if "CASH FLOW FROM OPERATING ACTIVITIES" in line.upper():
                in_cash_flow = True

            if in_cash_flow:
                cash_flow_lines.append((page_number, line))
                if "CASH & CASH EQUIVALENTS AT END" in line.upper():
                    found_cash_flow_end = True
                    break

        if found_cash_flow_end:
            break

    if cash_flow_lines:
        records.extend(parse_cash_flow(cash_flow_lines))

    # A duplicate key includes statement section and source page. Repeated
    # metric names in different cash-flow sections are not duplicates.
    duplicate_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = (
            record.get("statement"),
            record.get("section"),
            record.get("metric"),
            record.get("entity"),
            record.get("period_label"),
            record.get("source_page"),
        )
        duplicate_groups[key].append(record)

    duplicates = []
    for key, group in duplicate_groups.items():
        if len(group) > 1:
            duplicates.append({
                "key": list(key),
                "count": len(group),
                "source_texts": [item.get("source_text") for item in group],
            })

    # Structural completeness is not proof of financial accuracy.
    incomplete_rows = find_incomplete_metric_rows(records)

    status_counts = Counter(
        record.get("value_status", "unknown") for record in records
    )
    verification_counts = Counter(
        record.get("verification_status", "unknown") for record in records
    )

    reported_dashes = [
        {
            "statement": r.get("statement"),
            "section": r.get("section"),
            "metric": r.get("metric"),
            "entity": r.get("entity"),
            "period_label": r.get("period_label"),
            "source_page": r.get("source_page"),
            "source_text": r.get("source_text"),
        }
        for r in records
        if r.get("value_status") == "reported_dash"
    ]

    unparsed_values = [
        {
            "statement": r.get("statement"),
            "section": r.get("section"),
            "metric": r.get("metric"),
            "entity": r.get("entity"),
            "period_label": r.get("period_label"),
            "raw_value": r.get("raw_value"),
            "source_page": r.get("source_page"),
            "source_text": r.get("source_text"),
        }
        for r in records
        if r.get("value_status") == "unparsed"
    ]

    return {
        "schema_version": 1,
        "audit_generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "document": {
            "filename": pdf_path.name,
            "sha256": sha256_file(pdf_path),
            "page_count": len(reader.pages),
        },
        "audit_scope": {
            "financial_position": "all pages; recognized statement rows only",
            "profit_or_loss": "all pages; recognized statement rows only",
            "cash_flow": "from operating-activities heading through ending cash row",
            "financial_figures_independently_verified": False,
        },
        "summary": {
            "parsed_record_count": len(records),
            "records_by_statement": dict(Counter(
                r.get("statement", "unknown") for r in records
            )),
            "expected_columns_by_statement": dict(EXPECTED_COLUMNS),
            "value_status_counts": dict(status_counts),
            "verification_status_counts": dict(verification_counts),
            "duplicate_key_count": len(duplicates),
            "incomplete_metric_row_count": len(incomplete_rows),
            "reported_dash_count": len(reported_dashes),
            "unparsed_value_count": len(unparsed_values),
            "cash_flow_start_found": bool(cash_flow_lines),
            "cash_flow_end_found": found_cash_flow_end,
        },
        "checks": {
            "duplicate_keys": duplicates,
            "incomplete_metric_rows": incomplete_rows,
            "reported_dashes": reported_dashes,
            "unparsed_values": unparsed_values,
        },
        "records": records,
        "limitations": [
            "Parsed values remain unverified against the original table layout.",
            "Text extraction may lose visual column alignment.",
            "A structurally complete row is not proof that its values map to the correct columns.",
            "Reported dashes are preserved as missing/reported-dash values, not converted to zero.",
            "No financial ratios, conclusions, or investment recommendations are produced.",
        ],
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Audit extracted insurance statement structure."
    )
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = audit_report(args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = result["summary"]
    print("Insurance report audit completed.")
    print("PDF:", args.pdf.resolve())
    print("Output:", args.output.resolve())
    print("Pages:", result["document"]["page_count"])
    print("Parsed records:", summary["parsed_record_count"])
    print("Records by statement:", summary["records_by_statement"])
    print("Duplicate keys:", summary["duplicate_key_count"])
    print("Incomplete metric rows:", summary["incomplete_metric_row_count"])
    print("Reported dashes:", summary["reported_dash_count"])
    print("Unparsed values:", summary["unparsed_value_count"])
    print("Cash-flow start/end found:",
          summary["cash_flow_start_found"],
          summary["cash_flow_end_found"])
    print("Financial figures independently verified: No")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
