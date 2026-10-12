"""Reusable SearXNG search client for LibreChat's Python adapter."""

import json
import os
import sys
from urllib.parse import urlparse

import requests


SEARXNG_BASE_URL = os.getenv(
    "SEARXNG_BASE_URL",
    "http://localhost:8080",
).rstrip("/")

DEFAULT_TIMEOUT = 20
MAX_RESULTS = 8


class SearXNGError(RuntimeError):
    """Raised when SearXNG cannot provide usable search results."""


def search_web(query, max_results=MAX_RESULTS, categories="general"):
    """Search the web and return normalized results with source metadata."""
    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20.")

    endpoint = f"{SEARXNG_BASE_URL}/search"

    try:
        response = requests.get(
            endpoint,
            params={
                "q": query,
                "format": "json",
                "categories": categories,
            },
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": "LibreChat-ResearchClient/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SearXNGError(
            f"Could not reach SearXNG at {endpoint}: {exc}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise SearXNGError(
            "SearXNG did not return JSON. Check its JSON format configuration."
        ) from exc

    if not isinstance(payload, dict):
        raise SearXNGError(
            "SearXNG returned an unexpected JSON response type."
        )

    raw_results = payload.get("results", [])
    if not isinstance(raw_results, list):
        raise SearXNGError(
            "SearXNG returned an invalid results field."
        )

    results = []
    seen_urls = set()

    for item in raw_results:
        if not isinstance(item, dict):
            raise SearXNGError(
                "SearXNG returned a malformed search result."
            )

        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()

        if not url or not title:
            continue

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue

        if url in seen_urls:
            continue
        seen_urls.add(url)

        results.append({
            "title": title,
            "url": url,
            "domain": parsed.netloc.lower(),
            "snippet": (item.get("content") or "").strip(),
            "published_date": item.get("publishedDate"),
            "engines": item.get("engines") or [],
        })

        if len(results) >= max_results:
            break

    return {
        "query": query,
        "result_count": len(results),
        "results": results,
    }


def search_insurance_research(company=None, country=None, topic=None):
    """Build a focused public-source search for insurance research."""
    terms = [
        company or "insurance companies",
        country or "",
        topic or "annual report financial results industry benchmarks",
        "official report",
    ]

    query = " ".join(term.strip() for term in terms if term.strip())
    return search_web(query)


def main():
    query = " ".join(sys.argv[1:]).strip()

    if not query:
        print(
            'Usage: python searxng_client.py '
            '"insurance company annual report Nepal"'
        )
        raise SystemExit(2)

    try:
        result = search_web(query)
    except (SearXNGError, ValueError) as exc:
        print(f"SEARCH FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
