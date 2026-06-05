# -*- coding: utf-8 -*-
"""Arxiv API tools for paper search and detail retrieval."""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

from agentscope.tool._response import ToolChunk
from agentscope.message import TextBlock

from .utils import (
    create_http_client,
    extract_arxiv_paper_info,
    format_paper_summary,
    format_paper_detail,
    ARXIV_NS,
)

ARXIV_API = "http://export.arxiv.org/api/query"

# Papers output directory (relative to project root)
_PAPERS_DIR = Path(__file__).parent.parent / "papers"


def _save_papers(papers: list[dict], query: str = "") -> Path | None:
    """Save paper data to local JSON files.

    Each paper is saved individually as {arxiv_id}.json.
    A search index file is also created with the full result set.

    Args:
        papers: List of paper info dicts from extract_arxiv_paper_info.
        query: Search query string (for naming the index file).

    Returns:
        Path to the search index file, or None if save failed.
    """
    try:
        _PAPERS_DIR.mkdir(parents=True, exist_ok=True)

        # Save each paper individually
        for paper in papers:
            paper_path = _PAPERS_DIR / f"{paper['arxiv_id']}.json"
            paper_path.write_text(
                json.dumps(paper, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        # Save search index
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = "".join(c if c.isalnum() or c in "_-" else "_" for c in query)[:50]
        index_path = _PAPERS_DIR / f"search_{timestamp}_{safe_query}.json"
        index_path.write_text(
            json.dumps(
                {
                    "query": query,
                    "timestamp": timestamp,
                    "count": len(papers),
                    "papers": [p["arxiv_id"] for p in papers],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return index_path
    except Exception:
        return None


async def search_arxiv(
    query: str,
    max_results: int = 5,
    sort_by: str = "relevance",
) -> ToolChunk:
    """Search for papers on arxiv by keyword or topic.

    Use this tool to discover papers related to a research question.
    Returns paper titles, authors, abstract snippets, arxiv IDs, and PDF links.

    Args:
        query: Search keywords, e.g. "large language model agents".
        max_results: Number of papers to return (1-10, default 5).
        sort_by: Sort order — "relevance" or "lastUpdatedDate".
    """
    if max_results < 1 or max_results > 10:
        return ToolChunk(
            content=[
                TextBlock(
                    text=f"max_results must be between 1 and 10, got {max_results}."
                )
            ],
            state="error",
        )

    sort_param = "submittedDate" if sort_by == "lastUpdatedDate" else "relevance"
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_param,
    }

    async with create_http_client() as client:
        resp = await client.get(ARXIV_API, params=params)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entries = root.findall("./atom:entry", ARXIV_NS)

    if not entries:
        return ToolChunk(
            content=[
                TextBlock(
                    text=f"No papers found for query: '{query}'. "
                    f"Try different or broader keywords."
                )
            ],
        )

    papers = [extract_arxiv_paper_info(e) for e in entries]

    # Save papers to local files
    saved_path = _save_papers(papers, query)

    lines = [
        f"## Arxiv Search Results for: *{query}*",
        f"Found **{len(papers)}** papers.\n",
    ]
    if saved_path:
        lines.append(f"📁 Papers saved to: `{_PAPERS_DIR.resolve()}`\n")
    for i, paper in enumerate(papers, 1):
        snippet = paper["summary"][:400]
        if len(paper["summary"]) > 400:
            snippet += "..."
        lines.append(format_paper_summary(paper, index=i))
        lines.append(f"  *Abstract snippet*: {snippet}\n")

    return ToolChunk(
        content=[TextBlock(text="\n".join(lines))],
        metadata={"papers": papers, "query": query, "total_found": len(papers)},
    )


async def get_paper_detail(paper_id: str) -> ToolChunk:
    """Fetch the full abstract and metadata for a specific arxiv paper by its ID.

    Use this tool to read a paper's complete abstract before analyzing it.

    Args:
        paper_id: Arxiv paper ID, e.g. "2402.14034" or "2402.14034v1".
    """
    params = {"id_list": paper_id.strip(), "max_results": 1}

    async with create_http_client() as client:
        resp = await client.get(ARXIV_API, params=params)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entry = root.find("./atom:entry", ARXIV_NS)

    if entry is None:
        return ToolChunk(
            content=[
                TextBlock(
                    text=f"Paper '{paper_id}' not found on arxiv. "
                    f"Double-check the ID and try again."
                )
            ],
            state="error",
        )

    paper = extract_arxiv_paper_info(entry)
    _save_papers([paper], paper["arxiv_id"])
    detail_text = format_paper_detail(paper)

    return ToolChunk(
        content=[TextBlock(text=detail_text)],
        metadata={"paper": paper},
    )
