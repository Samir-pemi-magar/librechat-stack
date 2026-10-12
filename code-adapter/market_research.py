"""Evidence collection for industry-aware market research.

Search results are leads for research, not verified financial evidence.
This module does not calculate or assert competitor financial metrics.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from searxng_client import SearXNGError, search_web


BASE_DIR = Path(__file__).resolve().parent
RESEARCH_DIR = BASE_DIR / "reports" / "research"


def classify_domain(url):
    """Classify a domain as a research lead, not as verified evidence."""
    host = (urlparse(url).hostname or "").lower().rstrip(".")

    if host == "nia.gov.np" or host.endswith(".nia.gov.np"):
        return "insurance_regulator_domain_candidate"

    if host.endswith(".gov.np"):
        return "nepal_government_domain_candidate"

    if host.endswith(".com.np"):
        return "company_domain_candidate"

    return "other_domain"


def build_insurance_queries(country="Nepal", company=None, topic=None):
    """Build focused queries for regulator data and company comparisons."""
    country = (country or "Nepal").strip()
    topic = (topic or "premiums claims financial performance").strip()

    queries = [
        (
            f"{country} Insurance Authority official insurance industry "
            "statistics premiums claims annual report"
        ),
        (
            f"{country} insurance companies annual report "
            f"financial statements {topic} official"
        ),
    ]

    if company and company.strip():
        name = company.strip()
        queries.append(
            f'"{name}" {country} insurance annual report '
            "premiums claims financial statements"
        )
    else:
        queries.append(
            f"{country} insurance company annual reports "
            "solvency ratio claims ratio premium income"
        )

    # Preserve query order while removing accidental duplicates.
    return list(dict.fromkeys(queries))


def search_insurance_market(
    country="Nepal",
    company=None,
    topic=None,
    max_results_per_query=5,
):
    """Collect source metadata from SearXNG without asserting its accuracy."""
    if not 1 <= max_results_per_query <= 10:
        raise ValueError("max_results_per_query must be between 1 and 10.")

    queries = build_insurance_queries(country, company, topic)
    collected = []
    seen_urls = set()
    errors = []

    for query in queries:
        try:
            response = search_web(
                query,
                max_results=max_results_per_query,
            )
        except (SearXNGError, ValueError) as exc:
            errors.append({
                "query": query,
                "error": str(exc),
            })
            continue

        for result in response["results"]:
            url = result["url"]

            if url in seen_urls:
                continue

            seen_urls.add(url)
            collected.append({
                "title": result["title"],
                "url": url,
                "domain": result["domain"],
                "domain_classification": classify_domain(url),
                "snippet": result["snippet"],
                "published_date": result.get("published_date"),
                "search_engines": result.get("engines", []),
                "matched_query": query,
                "evidence_status": "discovered_not_verified",
            })

    return {
        "research_type": "insurance_market_research",
        "country": country,
        "company_requested": company,
        "topic": topic or "premiums claims financial performance",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "queries": queries,
        "source_count": len(collected),
        "sources": collected,
        "search_errors": errors,
        "interpretation_rules": [
            "Search snippets are leads, not verified financial facts.",
            "Domain classification is heuristic and does not authenticate a source.",
            "Open the original publication before using a figure as a benchmark.",
            "Compare only compatible metrics, currencies, accounting definitions, "
            "and reporting periods.",
            "If evidence is unavailable or incomparable, report that limitation.",
        ],
    }


def main():
    company = " ".join(sys.argv[1:]).strip() or None

    try:
        research = search_insurance_market(company=company)
    except (SearXNGError, ValueError) as exc:
        print(f"Research failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    filename = (
        "nepal_insurance_research.json"
        if not company
        else "nepal_insurance_company_research.json"
    )
    output_path = RESEARCH_DIR / filename
    output_path.write_text(
        json.dumps(research, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Research sources collected: {research['source_count']}")
    print(f"Research JSON saved: {output_path}")
    print(f"Search errors: {len(research['search_errors'])}")

    for source in research["sources"]:
        print(f"\n- {source['title']}")
        print(f"  URL: {source['url']}")
        print(f"  Domain category: {source['domain_classification']}")
        print(f"  Evidence status: {source['evidence_status']}")


if __name__ == "__main__":
    main()
