from __future__ import annotations

from dataclasses import dataclass
import json
from urllib import error, parse, request
from urllib.parse import quote

from .config import REQUEST_TIMEOUT_SECONDS, WIKIPEDIA_API_URL


@dataclass
class WikipediaDocument:
    title: str
    source_url: str
    text: str


class WikipediaIngestionError(RuntimeError):
    """Raised when Wikipedia content cannot be fetched."""


def fetch_wikipedia_page(title: str) -> WikipediaDocument:
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "redirects": 1,
        "format": "json",
        "titles": title,
    }
    try:
        url = f"{WIKIPEDIA_API_URL}?{parse.urlencode(params)}"
        req = request.Request(url, headers={"User-Agent": "LocalWikiRAG/1.0 (Python)"})
        with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise WikipediaIngestionError(
            f"Failed to fetch '{title}' from Wikipedia."
        )
    except Exception as exc:
        raise WikipediaIngestionError(f"Failed to fetch '{title}' from Wikipedia.") from exc
    pages = payload.get("query", {}).get("pages", {})
    if not pages:
        raise WikipediaIngestionError(f"Wikipedia returned no pages for '{title}'.")

    page = next(iter(pages.values()))
    extract = (page.get("extract") or "").strip()
    page_title = page.get("title", title)

    if not extract:
        raise WikipediaIngestionError(f"Wikipedia returned empty content for '{title}'.")

    source_url = f"https://en.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}"
    return WikipediaDocument(title=page_title, source_url=source_url, text=extract)
