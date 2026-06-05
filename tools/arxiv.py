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
    except Exception as e:
        print(f"[arxiv] ⚠️ 保存论文失败: {e}", flush=True)
        return None


async def search_arxiv(
    query: str,
    max_results: int = 5,
    sort_by: str = "relevance",
    year_from: int = 0,
) -> ToolChunk:
    """Search for papers on arxiv by keyword or topic.

    Use this tool to discover papers related to a research question.
    Returns paper titles, authors, abstract snippets, arxiv IDs, and PDF links.

    Args:
        query: Search keywords, e.g. "large language model agents 2025".
        max_results: Number of papers to return (1-10, default 5).
        sort_by: Sort order — "relevance" or "lastUpdatedDate".
        year_from: Minimum publication year. Papers older than this are
            discarded BEFORE saving. 0 = no filter. Set this to ensure
            only recent papers are kept, e.g. year_from=2025.
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

    all_papers = [extract_arxiv_paper_info(e) for e in entries]

    # Filter by year BEFORE saving — old papers never touch disk
    if year_from > 0:
        papers = [p for p in all_papers if _parse_pub_year(p) >= year_from]
        dropped = len(all_papers) - len(papers)
    else:
        papers = all_papers
        dropped = 0

    # Save only filtered papers
    saved_path = _save_papers(papers, query)

    lines = [
        f"## Arxiv Search Results for: *{query}*",
        f"Found **{len(all_papers)}** papers.",
    ]
    if year_from > 0:
        lines.append(f"Year filter (≥{year_from}): **{len(papers)}** kept, "
                     f"**{dropped}** discarded before saving.\n")
    else:
        lines.append("")
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

    First checks the local papers/ directory. If the paper was already saved
    by search_arxiv, it returns the cached data directly without calling the
    arxiv API. Only requests arxiv if the paper is not found locally.

    Args:
        paper_id: Arxiv paper ID, e.g. "2402.14034" or "2402.14034v1".
    """
    pid = paper_id.strip()

    # ── 1. Try local cache first ──────────────────────────────────────
    if _PAPERS_DIR.exists():
        local = _PAPERS_DIR / f"{pid}.json"
        if not local.exists():
            # Try partial match (e.g., "2402.14034" matches "2402.14034v1.json")
            matches = list(_PAPERS_DIR.glob(f"{pid}*.json"))
            if matches:
                local = matches[0]
        if local.exists():
            try:
                paper = json.loads(local.read_text(encoding="utf-8"))
                detail_text = format_paper_detail(paper)
                return ToolChunk(
                    content=[TextBlock(text=detail_text)],
                    metadata={"paper": paper, "source": "local"},
                )
            except Exception:
                pass  # Corrupted file, fall through to API

    # ── 2. Fetch from arxiv API ───────────────────────────────────────
    params = {"id_list": pid, "max_results": 1}

    async with create_http_client() as client:
        resp = await client.get(ARXIV_API, params=params)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entry = root.find("./atom:entry", ARXIV_NS)

    if entry is None:
        return ToolChunk(
            content=[
                TextBlock(
                    text=f"Paper '{pid}' not found on arxiv or locally. "
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
        metadata={"paper": paper, "source": "arxiv_api"},
    )


def _parse_pub_year(paper: dict) -> int:
    """Extract publication year from a paper dict."""
    return int(paper.get("published", "0")[:4])


async def filter_papers_by_year(year_from: int = 0, year_to: int = 9999,
                                 years: str = "") -> ToolChunk:
    """Filter saved papers by publication year. Supports three modes:

    - Range: set year_from and/or year_to (e.g. year_from=2024, year_to=2026)
    - Exact years: pass a comma-separated years string (e.g. years="2022,2024,2026")
    - Both: combine range with specific years (e.g. year_from=2023, years="2025")

    Papers not matching the filter are permanently deleted from disk.

    Args:
        year_from: Minimum publication year (inclusive). 0 = no lower bound.
        year_to: Maximum publication year (inclusive). 9999 = no upper bound.
        years: Comma-separated specific years to also keep, e.g. "2022,2024".
               Papers matching any of these years are kept regardless of range.
    """
    if not _PAPERS_DIR.exists():
        return ToolChunk(
            content=[TextBlock(text="No papers directory found. Run search_arxiv first.")],
        )

    # Parse specific years
    specific_years: set[int] = set()
    for part in years.replace(" ", "").split(","):
        part = part.strip()
        if part.isdigit():
            specific_years.add(int(part))

    kept: list[dict] = []
    removed: list[str] = []

    for paper_file in sorted(_PAPERS_DIR.glob("*.json")):
        if paper_file.name.startswith("search_"):
            continue
        try:
            paper = json.loads(paper_file.read_text(encoding="utf-8"))
            pub_year = _parse_pub_year(paper)
            info = f"{paper['arxiv_id']} ({paper.get('published', '?')[:10]})"

            in_range = year_from <= pub_year <= year_to
            in_specific = pub_year in specific_years

            if in_range or in_specific:
                kept.append(paper)
            else:
                paper_file.unlink()
                removed.append(info)
        except Exception:
            continue

    # Build readable description of the filter
    conditions: list[str] = []
    if year_from > 0 and year_to < 9999:
        conditions.append(f"{year_from}-{year_to}年")
    elif year_from > 0:
        conditions.append(f"{year_from}年及之后")
    elif year_to < 9999:
        conditions.append(f"{year_to}年及之前")
    if specific_years:
        conditions.append(f"特别保留 {sorted(specific_years)} 年")
    desc = " + ".join(conditions) if conditions else "无过滤"

    lines = [
        f"## 论文时间过滤: {desc}",
        f"- ✅ 保留: **{len(kept)}** 篇",
        f"- 🗑 删除: **{len(removed)}** 篇",
    ]
    if removed:
        lines.append("\n已删除:")
        for r in removed:
            lines.append(f"  - `{r}`")
    if kept:
        lines.append(f"\n保留:")
        for p in kept:
            lines.append(f"  - `{p['arxiv_id']}` ({_parse_pub_year(p)}年) — {p['title'][:70]}")
    return ToolChunk(content=[TextBlock(text="\n".join(lines))])


async def remove_paper(paper_id: str) -> ToolChunk:
    """Delete a single irrelevant paper from disk.

    Use this after reviewing a paper's title and abstract to remove it if it
    does not relate to the research topic.  Relevance is judged by YOU (the
    LLM) — read the paper's title and abstract, compare against the user's
    research question, and call this tool to delete the paper if it is
    unrelated.

    Args:
        paper_id: Arxiv paper ID, e.g. "2402.14034" or "2402.14034v1".
    """
    if not _PAPERS_DIR.exists():
        return ToolChunk(
            content=[TextBlock(text="No papers directory. Nothing to remove.")],
        )

    target = _PAPERS_DIR / f"{paper_id}.json"
    if not target.exists():
        # Try partial match
        matches = list(_PAPERS_DIR.glob(f"{paper_id}*.json"))
        if matches:
            target = matches[0]
        else:
            return ToolChunk(
                content=[TextBlock(text=f"Paper '{paper_id}' not found on disk.")],
            )

    try:
        paper = json.loads(target.read_text(encoding="utf-8"))
        title = paper.get("title", "?")[:80]
        target.unlink()
        return ToolChunk(
            content=[TextBlock(text=f"🗑 已删除: `{paper_id}` — {title}")],
        )
    except Exception as e:
        return ToolChunk(
            content=[TextBlock(text=f"删除失败: {e}")],
            state="error",
        )
