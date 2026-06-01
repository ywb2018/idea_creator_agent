# -*- coding: utf-8 -*-
"""Shared utilities for tool implementations."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

import httpx

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 30.0

# Arxiv API namespace
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def create_http_client(timeout: float = DEFAULT_TIMEOUT) -> httpx.AsyncClient:
    """Create a reusable async HTTP client with consistent settings.

    Args:
        timeout: Request timeout in seconds.

    Returns:
        Configured httpx.AsyncClient instance.
    """
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "IdeaCreator/1.0 (research-agent)"},
    )


def extract_arxiv_paper_info(entry: ET.Element) -> dict:
    """Parse a single arxiv API <entry> element into a flat dict.

    Args:
        entry: The XML <entry> element from arxiv's Atom response.

    Returns:
        A dict with keys: id, title, summary, published, authors,
        categories, pdf_url, arxiv_id.
    """
    ns = ARXIV_NS

    def _text(path: str, default: str = "") -> str:
        return (entry.findtext(path, default, ns) or default).strip()

    arxiv_id = ""
    raw_id = _text("./atom:id")
    if raw_id:
        # Extract just the ID portion: "http://arxiv.org/abs/2402.14034v1" -> "2402.14034v1"
        arxiv_id = raw_id.split("/")[-1]

    pdf_url = ""
    for link in entry.findall("./atom:link", ns):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
            break

    return {
        "id": raw_id,
        "arxiv_id": arxiv_id,
        "title": _text("./atom:title").replace("\n", " "),
        "summary": _text("./atom:summary").replace("\n", " "),
        "published": _text("./atom:published"),
        "authors": [
            (a.findtext("atom:name", "", ns) or "").strip()
            for a in entry.findall("./atom:author", ns)
        ],
        "categories": [
            c.get("term", "") for c in entry.findall("./atom:category", ns)
        ],
        "pdf_url": pdf_url,
    }


def format_paper_summary(paper: dict, index: Optional[int] = None) -> str:
    """Format a paper dict into a readable markdown summary.

    Args:
        paper: Paper info dict from extract_arxiv_paper_info().
        index: Optional 1-based index for numbered lists.

    Returns:
        Formatted markdown string.
    """
    prefix = f"### {index}. " if index else "### "
    lines = [
        f"{prefix}{paper['title']}",
        f"- **ID**: `{paper['arxiv_id']}`",
        f"- **Authors**: {', '.join(paper['authors'][:5])}"
        f"{' et al.' if len(paper['authors']) > 5 else ''}",
        f"- **Published**: {paper['published']}",
        f"- **Categories**: {', '.join(paper['categories'][:5])}",
        f"- **PDF**: {paper['pdf_url'] or 'N/A'}",
    ]
    return "\n".join(lines)


def format_paper_detail(paper: dict) -> str:
    """Format a paper dict into a full-detail markdown view.

    Args:
        paper: Paper info dict from extract_arxiv_paper_info().

    Returns:
        Formatted markdown string with full abstract.
    """
    lines = [
        f"## {paper['title']}",
        f"**ID**: `{paper['arxiv_id']}` | **Published**: {paper['published']}",
        f"**Authors**: {', '.join(paper['authors'])}",
        f"**Categories**: {', '.join(paper['categories'])}",
        f"**PDF**: {paper['pdf_url'] or 'N/A'}",
        "",
        "### Abstract",
        paper["summary"],
    ]
    return "\n".join(lines)
