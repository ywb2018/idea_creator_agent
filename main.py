#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CLI entry point for Idea Creator.

Usage:
    python main.py "research question"
    python main.py "research question" --agents chief,searcher
    python main.py "research question" --strategy pipeline
    python main.py "research question" --config orchestration.yaml

Environment:
    DEEPSEEK_API_KEY — set in .env or environment variable.
"""

import argparse
import asyncio


async def main_async(args: argparse.Namespace) -> None:
    """Async main — builds team, runs research."""
    from idea_creator import research

    agent_names = None
    if args.agents:
        agent_names = [n.strip() for n in args.agents.split(",")]

    result = await research(
        query=args.query,
        agent_names=agent_names,
        api_key=args.api_key,
        config=args.config,
        strategy=args.strategy,
        max_rounds=args.max_rounds,
        verbose=not args.quiet,
    )
    print(result)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="idea-creator",
        description="Search papers, analyze research, and generate novel ideas "
        "using a multi-agent research team.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "LLM agents for code generation"
  python main.py "open problems in ML" --agents chief,searcher,ideator
  python main.py "survey RLHF" --strategy pipeline
  python main.py "review RLHF" --config orchestration.yaml
        """,
    )
    parser.add_argument("query", help="Research question or topic.")
    parser.add_argument(
        "--agents", "-a", default=None,
        help="Comma-separated agent names (default: all in definitions/).",
    )
    parser.add_argument(
        "--config", "-c", default=None,
        help="Path to YAML orchestration config file.",
    )
    parser.add_argument(
        "--strategy", "-s", default="autonomous",
        choices=["autonomous", "pipeline"],
        help="Orchestration strategy (default: autonomous).",
    )
    parser.add_argument(
        "--max-rounds", "-r", type=int, default=15,
        help="Max delegation rounds (default: 15).",
    )
    parser.add_argument(
        "--api-key", "-k", default=None,
        help="DeepSeek API key (or set DEEPSEEK_API_KEY env var).",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress agent interaction logging.",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
