from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re

app = FastAPI(title="Prarambha Local Scraper", version="1.0.0")


class ScrapeRequest(BaseModel):
    url: str
    formats: list[str] = ["markdown"]
    onlyMainContent: bool = True


def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove elements that are normally not useful to an LLM.
    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "footer",
        "header",
        "form",
        "iframe",
    ]):
        tag.decompose()

    root = soup

    # Prefer the main article/content when available.
    for selector in ["article", "main", "[role='main']"]:
        candidate = soup.select_one(selector)
        if candidate:
            root = candidate
            break

    text = root.get_text("\n", strip=True)

    # Normalize excessive whitespace.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "local-scraper",
    }


@app.post("/v2/scrape")
def scrape(request: ScrapeRequest):
    url = request.url.strip()

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Only HTTP and HTTPS URLs are supported",
        )

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; PrarambhaLocalScraper/1.0)"
                )
            },
            timeout=15,
            allow_redirects=True,
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        return {
            "success": False,
            "error": f"Failed to fetch URL: {exc}",
        }

    content_type = response.headers.get("content-type", "").lower()

    if "text/html" not in content_type:
        text = response.text
    else:
        text = clean_text(response.text)

    if not text:
        return {
            "success": False,
            "error": "No readable content extracted",
        }

    soup = BeautifulSoup(response.text, "html.parser")

    title = ""
    if soup.title:
        title = soup.title.get_text(" ", strip=True)

    return {
        "success": True,
        "data": {
            "markdown": text,
            "metadata": {
                "sourceURL": response.url,
                "url": response.url,
                "title": title,
                "statusCode": response.status_code,
                "description": "",
            },
        },
    }
