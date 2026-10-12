"""Explicit, conservative parsers for insurance financial statements."""

from __future__ import annotations

import re
from typing import Any


NUMBER_TOKEN_RE = re.compile(
    r"\(\s*-?\d[\d,]*(?:\.\d+)?\s*\)"
    r"|-?\d[\d,]*(?:\.\d+)?"
    r"|(?<!\S)-(?!\S)"
)

FINANCIAL_POSITION_COLUMNS = (
    {
        "entity": "Group",
        "period_label": "At the end of this Quarter",
    },
    {
        "entity": "Group",
        "period_label": "At the end of Immediate Previous Year",
    },
    {
        "entity": "Insurance Company",
        "period_label": "At the end of this Quarter",
    },
    {
        "entity": "Insurance Company",
        "period_label": "At the end of Immediate Previous Year",
    },
)


def parse_value(raw_value: str) -> tuple[int | float | None, str]:
    """Parse a displayed value without treating a dash as numeric zero."""
    raw = raw_value.strip()

    if raw == "-":
        return None, "reported_dash"

    negative = raw.startswith("(") and raw.endswith(")")
    normalized = raw.strip("()").replace(",", "").strip()

    try:
        number = float(normalized) if "." in normalized else int(normalized)
    except ValueError:
        return None, "unparsed"

    if negative:
        number = -number

    return number, "numeric_unverified"


def parse_financial_position(
    lines: list[str],
    page_number: int = 1,
) -> list[dict[str, Any]]:
    """Parse only the recognized four-column financial-position section.

    Column mappings are explicit. Records remain unverified until reviewed
    against the original report.
    """
    start = next(
        (
            i for i, line in enumerate(lines)
            if "CONDENSED CONSOLIDATED STATEMENT OF FINANCIAL POSITION"
            in line.upper()
        ),
        None,
    )
    if start is None:
        return []

    end = next(
        (
            i for i in range(start + 1, len(lines))
            if "CONDENSED CONSOLIDATED STATEMENT OF PROFIT OR LOSS"
            in lines[i].upper()
        ),
        len(lines),
    )

    records: list[dict[str, Any]] = []

    for line in lines[start + 1:end]:
        matches = list(NUMBER_TOKEN_RE.finditer(line))
        if len(matches) != 4:
            continue

        label = line[:matches[0].start()].strip().rstrip(":").strip()
        if not label:
            continue

        for column_index, match in enumerate(matches):
            column = FINANCIAL_POSITION_COLUMNS[column_index]
            raw_value = match.group(0).strip()
            value, value_status = parse_value(raw_value)

            records.append({
                "statement": "Condensed Consolidated Statement of Financial Position",
                "metric": label,
                "entity": column["entity"],
                "period_label": column["period_label"],
                "value": value,
                "raw_value": raw_value,
                "unit": "NPR",
                "source_page": page_number,
                "source_text": line,
                "value_status": value_status,
                "verification_status": "parsed_unverified",
            })

    return records


PROFIT_LOSS_COLUMNS = (
    {
        "entity": "Group",
        "period_label": "Current year - This Quarter",
    },
    {
        "entity": "Group",
        "period_label": "Current year - YTD",
    },
    {
        "entity": "Group",
        "period_label": "Corresponding previous year - This Quarter",
    },
    {
        "entity": "Group",
        "period_label": "Corresponding previous year - YTD",
    },
    {
        "entity": "Insurance Company",
        "period_label": "Current year - This Quarter",
    },
    {
        "entity": "Insurance Company",
        "period_label": "Current year - YTD",
    },
    {
        "entity": "Insurance Company",
        "period_label": "Corresponding previous year - This Quarter",
    },
    {
        "entity": "Insurance Company",
        "period_label": "Corresponding previous year - YTD",
    },
)


def parse_profit_or_loss(
    lines: list[str],
    page_number: int = 1,
) -> list[dict[str, Any]]:
    """Parse unambiguous eight-value rows in the profit-or-loss statement."""
    start = next(
        (
            i for i, line in enumerate(lines)
            if "CONDENSED CONSOLIDATED STATEMENT OF PROFIT OR LOSS"
            in line.upper()
        ),
        None,
    )
    if start is None:
        return []

    end = next(
        (
            i for i in range(start + 1, len(lines))
            if "CONDENSED CONSOLIDATED STATEMENT OF OTHER COMPREHENSIVE INCOME"
            in lines[i].upper()
        ),
        len(lines),
    )

    records: list[dict[str, Any]] = []

    for line in lines[start + 1:end]:
        matches = list(NUMBER_TOKEN_RE.finditer(line))
        if len(matches) != len(PROFIT_LOSS_COLUMNS):
            continue

        label = line[:matches[0].start()].strip().rstrip(":").strip()
        if not label:
            continue

        for column_index, match in enumerate(matches):
            column = PROFIT_LOSS_COLUMNS[column_index]
            raw_value = match.group(0).strip()
            value, value_status = parse_value(raw_value)

            records.append({
                "statement": "Condensed Consolidated Statement of Profit or Loss",
                "metric": label,
                "entity": column["entity"],
                "period_label": column["period_label"],
                "value": value,
                "raw_value": raw_value,
                "unit": "NPR",
                "source_page": page_number,
                "source_text": line,
                "value_status": value_status,
                "verification_status": "parsed_unverified",
            })

    return records


CASH_FLOW_COLUMNS = (
    {
        "entity": "Group",
        "period_label": "Current Year",
    },
    {
        "entity": "Group",
        "period_label": "Previous Year",
    },
    {
        "entity": "Insurance Company",
        "period_label": "Current Year",
    },
    {
        "entity": "Insurance Company",
        "period_label": "Previous Year",
    },
)

# Validate each complete whitespace-separated value, rather than
# searching for numeric substrings inside malformed values.
_CASH_FLOW_VALUE_RE = re.compile(
    r"(?:"
    r"\(\s*-?(?:\d{1,3}(?:,\d{3})+|\d{1,3})(?:\.\d+)?\s*\)"
    r"|-?(?:\d{1,3}(?:,\d{3})+|\d{1,3})(?:\.\d+)?"
    r"|-"
    r")"
)


def parse_cash_flow(
    lines: list[str] | list[tuple[int, str]],
    page_number: int = 6,
) -> list[dict[str, Any]]:
    """Parse cash-flow rows while retaining section and page context.

    Pass strings for one page or (page_number, line) pairs for multiple pages.
    Section context carries across consecutive input lines.
    """
    records: list[dict[str, Any]] = []
    current_section: str | None = None

    section_headings = (
        ("Cash Flow From Operating Activities", "Operating Activities"),
        ("Cash Flow From Investing Activities", "Investing Activities"),
        ("Cash Flow From Financing Activities", "Financing Activities"),
    )

    for item in lines:
        if isinstance(item, tuple):
            current_page, line = item
        else:
            current_page, line = page_number, item

        normalized_line = " ".join(line.split()).strip()
        normalized_lower = normalized_line.casefold()

        # These are report-wide reconciliation rows, not financing activities.
        reconciliation_prefixes = (
            "net increase/(decrease) in cash & cash equivalents",
            "cash & cash equivalents at beginning of the year/period",
            "cash & cash equivalents at end of the year/period",
            "components of cash & cash equivalents",
        )

        if normalized_lower.startswith(reconciliation_prefixes):
            row_section = "Cash and Cash Equivalents Reconciliation"
        else:
            row_section = None
            for heading, section_name in section_headings:
                if normalized_lower.startswith(heading.casefold()):
                    current_section = section_name
                    break

        if row_section is None:
            row_section = current_section

        tokens = normalized_line.split()
        if len(tokens) <= len(CASH_FLOW_COLUMNS):
            continue

        value_tokens = tokens[-len(CASH_FLOW_COLUMNS):]
        if not all(
            _CASH_FLOW_VALUE_RE.fullmatch(token)
            for token in value_tokens
        ):
            continue

        label = " ".join(tokens[:-len(CASH_FLOW_COLUMNS)])
        label = label.rstrip(":").strip()
        if not label:
            continue

        for column, raw_value in zip(CASH_FLOW_COLUMNS, value_tokens):
            value, value_status = parse_value(raw_value)
            records.append({
                "statement": "Consolidated Statement of Cash Flows",
                "section": row_section,
                "metric": label,
                "entity": column["entity"],
                "period_label": column["period_label"],
                "value": value,
                "raw_value": raw_value,
                "unit": "NPR",
                "source_page": current_page,
                "source_text": line,
                "value_status": value_status,
                "verification_status": "parsed_unverified",
            })

    return records
