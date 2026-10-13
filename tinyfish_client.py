"""Thin client for the TinyFish Search and Fetch APIs.

Request/response shapes follow the TinyFish docs (verified Oct 2026):
  Search: GET  https://api.search.tinyfish.ai?query=...   header X-API-Key
          -> {"query", "results": [{"position","site_name","title","snippet","url",...}],
              "total_results", "page"}
  Fetch:  POST https://api.fetch.tinyfish.ai              header X-API-Key
          body {"urls": [...], "format": "markdown"}
          -> {"results": [{"url","final_url","title","description","text",...}],
              "errors":  [{"url","error","status"?}]}

The API key is read from the TINYFISH_API_KEY environment variable and is never
logged, printed, or included in error messages.
"""
from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"

SEARCH_TIMEOUT_S = 30
FETCH_TIMEOUT_S = 150  # docs recommend >= 150s client timeout for Fetch
MAX_FETCH_URLS = 10

_HTTP_MESSAGES = {
    400: "TinyFish rejected the request (bad or missing parameter).",
    401: "TinyFish rejected the API key. Check TINYFISH_API_KEY.",
    402: "TinyFish free allowance is used up for today.",
    403: "TinyFish refused this request.",
    404: "This TinyFish API is not available.",
    422: "TinyFish could not process the request.",
    429: "Too many requests to TinyFish. Wait a moment and try again.",
    500: "TinyFish had an internal error. Try again shortly.",
    503: "TinyFish is temporarily unavailable. Try again shortly.",
}


class TinyFishError(Exception):
    """Raised for any TinyFish failure; the message is safe to show to users."""


def get_api_key() -> str | None:
    key = os.getenv("TINYFISH_API_KEY", "").strip()
    return key or None


def is_configured() -> bool:
    return get_api_key() is not None


def _headers() -> dict[str, str]:
    key = get_api_key()
    if not key:
        raise TinyFishError(
            "TINYFISH_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return {"X-API-Key": key}


def _check(resp: requests.Response) -> dict[str, Any]:
    if resp.status_code != 200:
        msg = _HTTP_MESSAGES.get(resp.status_code, f"TinyFish returned HTTP {resp.status_code}.")
        raise TinyFishError(msg)
    try:
        data = resp.json()
    except ValueError as exc:
        raise TinyFishError("TinyFish returned a response that was not valid JSON.") from exc
    if not isinstance(data, dict):
        raise TinyFishError("TinyFish returned an unexpected response shape.")
    return data


def search(query: str, *, location: str | None = None, language: str | None = None,
           page: int | None = None) -> list[dict[str, Any]]:
    """Run a web search. Returns the `results` list (possibly empty)."""
    query = (query or "").strip()
    if not query:
        raise TinyFishError("Please enter something to search for.")
    params: dict[str, Any] = {"query": query}
    if location:
        params["location"] = location
    if language:
        params["language"] = language
    if page is not None:
        params["page"] = page
    try:
        resp = requests.get(SEARCH_URL, params=params, headers=_headers(),
                            timeout=SEARCH_TIMEOUT_S)
    except requests.RequestException as exc:
        raise TinyFishError("Could not reach TinyFish Search (network problem).") from exc
    data = _check(resp)
    results = data.get("results", [])
    return results if isinstance(results, list) else []


def fetch(urls: list[str], *, fmt: str = "markdown") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch page content. Returns (results, errors) exactly as TinyFish reports them."""
    urls = [u for u in (urls or []) if u]
    if not urls:
        raise TinyFishError("No URL to fetch.")
    if len(urls) > MAX_FETCH_URLS:
        raise TinyFishError(f"TinyFish Fetch accepts at most {MAX_FETCH_URLS} URLs per request.")
    body = {"urls": urls, "format": fmt}
    try:
        resp = requests.post(FETCH_URL, json=body, headers=_headers(),
                             timeout=FETCH_TIMEOUT_S)
    except requests.RequestException as exc:
        raise TinyFishError("Could not reach TinyFish Fetch (network problem).") from exc
    data = _check(resp)
    results = data.get("results", [])
    errors = data.get("errors", [])
    return (results if isinstance(results, list) else [],
            errors if isinstance(errors, list) else [])


def fetch_page_text(url: str, max_chars: int = 3000) -> dict[str, str]:
    """Convenience wrapper: fetch one URL and return title + trimmed markdown text."""
    results, errors = fetch([url], fmt="markdown")
    if results:
        page = results[0]
        text = page.get("text")
        if not isinstance(text, str) or not text.strip():
            raise TinyFishError("The page was fetched but had no readable text.")
        text = text.strip()
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "…"
        return {"title": page.get("title") or url, "text": text,
                "url": page.get("final_url") or url}
    if errors:
        code = errors[0].get("error", "unknown")
        raise TinyFishError(f"TinyFish could not fetch that page ({code}).")
    raise TinyFishError("TinyFish returned no content for that page.")
