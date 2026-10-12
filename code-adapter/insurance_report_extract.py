"""Conservative, page-referenced extraction for insurance financial PDFs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


FINANCIAL_TERMS = (
    "premium", "claim", "profit", "loss", "investment",
    "solvency", "policy", "asset", "liabilit", "equity",
    "reserve", "insurance fund", "life fund", "cash flow",
    "insurance contract", "reinsurance", "capital",
    "income", "expense", "revenue", "actuarial",
)

PERIOD_PATTERNS = (
    re.compile(
        r"(?im)^\s*(?:For the Quarter Ended|Quarter Ended)\s+"
        r"([^\r\n]{1,120})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?im)^\s*For Period\s+([^\r\n]{1,120})",
        re.IGNORECASE,
    ),
)

NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z])"
    r"(?:\(\s*)?"
    r"(?:NPR\.?\s*)?"
    r"-?\d[\d,]*(?:\.\d+)?"
    r"(?:\s*\))?"
    r"|(?<!\w)-"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_lines(text: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]


def extract_report(pdf_path: Path) -> dict:
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported.")

    page_records = []
    candidates = []
    period_mentions = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines = clean_lines(text)

        page_records.append({
            "page": page_number,
            "text_available": bool(text.strip()),
            "character_count": len(text),
            "lines": lines,
        })

        for pattern in PERIOD_PATTERNS:
            for match in pattern.finditer(text):
                period_mentions.append({
                    "page": page_number,
                    "matched_text": match.group(0).strip(),
                    "candidate_period": match.group(1).strip(),
                    "verification_status": "needs_manual_confirmation",
                })

        for line_number, line in enumerate(lines, start=1):
            lowered = line.lower()
            matched_terms = [
                term for term in FINANCIAL_TERMS if term in lowered
            ]
            numbers = NUMBER_PATTERN.findall(line)

            if matched_terms and numbers:
                candidates.append({
                    "page": page_number,
                    "line": line_number,
                    "source_text": line,
                    "matched_terms": matched_terms,
                    "number_tokens": [
                        token.strip() for token in numbers
                    ],
                    "verification_status": "unverified_candidate",
                })

    metadata_path = pdf_path.with_suffix(".metadata.json")
    source_metadata = None

    if metadata_path.is_file():
        try:
            source_metadata = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            source_metadata = None

    return {
        "schema_version": 1,
        "document": {
            "filename": pdf_path.name,
            "sha256": sha256_file(pdf_path),
            "page_count": len(reader.pages),
            "source_metadata": source_metadata,
        },
        "extraction": {
            "method": "pypdf text extraction and conservative keyword matching",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "reporting_period": {
                "mentions": period_mentions,
                "status": "needs_manual_confirmation",
            },
            "page_text": page_records,
            "financial_candidates": candidates,
            "limitations": [
                "Keyword matches are candidates, not verified metrics.",
                "Number tokens may include dates, references, and table values.",
                "Column alignment and group/company scope are not inferred.",
                "Scanned or image-only content may not be extractable.",
                "No financial ratios or cross-company comparisons are calculated.",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    output = args.output or args.pdf.with_name(
        args.pdf.stem + "_extraction.json"
    )

    result = extract_report(args.pdf)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    extraction = result["extraction"]
    print("Extraction completed.")
    print("PDF:", args.pdf.resolve())
    print("Pages:", result["document"]["page_count"])
    print("Reporting-period mentions:",
          len(extraction["reporting_period"]["mentions"]))
    print("Financial candidate lines:",
          len(extraction["financial_candidates"]))
    print("Extractable-text pages:",
          sum(p["text_available"] for p in extraction["page_text"]))
    print("Output:", output.resolve())
    print("Verification status: candidates remain unverified")

    print("\nPeriod mentions:")
    for item in extraction["reporting_period"]["mentions"]:
        print(
            f"  Page {item['page']}: "
            f"{item['matched_text'][:180]}"
        )

    print("\nFirst 12 financial candidates:")
    for item in extraction["financial_candidates"][:12]:
        print(
            f"  p.{item['page']} line {item['line']}: "
            f"{item['source_text'][:180]}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
