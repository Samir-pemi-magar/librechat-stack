"""Heuristic industry detection based on analyzed workbook columns."""

import json
import re
import sys
from pathlib import Path


INDUSTRY_TERMS = {
    "insurance": [
        "insurance", "premium", "claims paid", "claims ratio",
        "loss ratio", "policy number", "policyholder",
        "underwriting", "reinsurance", "solvency",
    ],
    "retail": [
        "sku", "point of sale", "sold qty", "sales quantity",
        "inventory", "stock keeping", "store", "product category",
    ],
    "manufacturing": [
        "production", "machine hours", "defect rate",
        "raw material", "work in progress", "factory output",
    ],
    "general_finance": [
        "gross revenue", "operating expenses", "net profit",
        "reported profit", "ledger", "balance sheet", "cash flow",
    ],
}

INSURANCE_METRICS = {
    "premiums": ["premium", "written premium", "earned premium"],
    "claims": ["claim", "claims paid", "incurred claims"],
    "claims_ratio": ["claims ratio", "loss ratio", "claim ratio"],
    "reserves": ["reserve", "technical provision", "outstanding claims"],
    "solvency": ["solvency", "capital adequacy", "risk-based capital"],
    "policy_retention": ["renewal", "persistency", "policy retention", "lapse"],
    "underwriting": ["underwriting"],
    "reinsurance": ["reinsurance", "ceded premium", "recoverable"],
}


def normalize(value):
    return re.sub(r"\s+", " ", str(value).strip().lower())


def collect_columns(analysis):
    columns = []

    for sheet in analysis.get("sheets", []):
        if sheet.get("type") != "tabular":
            continue

        for column in sheet.get("columns", []):
            columns.append({
                "sheet": sheet.get("sheet", "unknown"),
                "column": str(column),
                "normalized": normalize(column),
            })

    return columns


def match_terms(columns, terms):
    matches = []

    for item in columns:
        normalized_column = item["normalized"]
        if any(
            re.search(
                rf"(?<!\w){re.escape(normalize(term))}(?!\w)",
                normalized_column,
            )
            for term in terms
        ):
            matches.append({
                "sheet": item["sheet"],
                "column": item["column"],
            })

    return matches


def profile_industry(analysis):
    columns = collect_columns(analysis)
    evidence = {}

    for industry, terms in INDUSTRY_TERMS.items():
        matches = match_terms(columns, terms)
        if matches:
            evidence[industry] = matches

    scores = {
        industry: len({
            (item["sheet"], item["column"])
            for item in matches
        })
        for industry, matches in evidence.items()
    }

    if not scores:
        detected = "general"
        confidence = "low"
    else:
        ranked = sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        detected = ranked[0][0]
        tied = len(ranked) > 1 and ranked[0][1] == ranked[1][1]

        runner_up_score = ranked[1][1] if len(ranked) > 1 else 0
        close_competition = (
            runner_up_score > 0
            and runner_up_score >= ranked[0][1] * 0.5
        )

        if tied or ranked[0][1] < 2 or close_competition:
            confidence = "low"
        elif ranked[0][1] >= 4:
            confidence = "high"
        else:
            confidence = "medium"

    insurance_metrics = {}

    for metric, terms in INSURANCE_METRICS.items():
        matches = match_terms(columns, terms)
        if matches:
            insurance_metrics[metric] = matches

    return {
        "workbook": analysis.get("file"),
        "detected_industry": detected,
        "confidence": confidence,
        "classification_method": (
            "Heuristic column-name matching; confirm against "
            "verified organization information."
        ),
        "industry_scores": scores,
        "industry_evidence": evidence,
        "insurance_metric_columns": insurance_metrics,
        "available_sheets": [
            {
                "sheet": sheet.get("sheet"),
                "type": sheet.get("type"),
                "data_rows": sheet.get("data_rows"),
                "columns": sheet.get("columns", []),
            }
            for sheet in analysis.get("sheets", [])
        ],
        "limitations": [
            "Column names alone cannot verify an organization's industry.",
            "A matching column does not prove its values are valid.",
            "No financial ratios or external benchmarks are calculated here.",
        ],
    }


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python industry_profile.py "
            "incoming/<workbook>_analysis.json"
        )
        raise SystemExit(2)

    path = Path(sys.argv[1])

    if not path.is_file():
        print(f"Analysis JSON not found: {path}", file=sys.stderr)
        raise SystemExit(1)

    try:
        analysis = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read analysis JSON: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    result = profile_industry(analysis)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
