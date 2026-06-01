#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CLI entry point for Idea Creator.

Usage:
    python main.py "research question" --preset quick_survey
    python main.py "research question" --preset idea_generation
    python main.py "research question" --config path/to/custom.yaml

Environment:
    DEEPSEEK_API_KEY — Your DeepSeek API key (or pass via --api-key).
"""

import argparse
import asyncio
import os
import sys


async def main_async(args: argparse.Namespace) -> None:
    """Async main — loads config, builds team, runs research."""
    # Import here so argparse --help is fast
    from idea_creator import research

    result = await research(
        query=args.query,
        preset=args.preset,
        config_path=args.config,
        api_key=args.api_key,
        verbose=not args.quiet,
    )

    print(result)


def main() -> None:
    """Parse arguments and run the async main."""
    parser = argparse.ArgumentParser(
        prog="idea-creator",
        description="Search papers, analyze research, and generate novel ideas "
        "using a multi-agent research team.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "LLM agents for code generation" --preset quick_survey
  python main.py "What are open problems in mechanistic interpretability?" --preset idea_generation
  python main.py "Survey RLHF alternatives" --config my_config.yaml
        """,
    )

    parser.add_argument(
        "query",
        help="Research question or topic to investigate.",
    )
    parser.add_argument(
        "--preset", "-p",
        default="quick_survey",
        choices=["quick_survey", "idea_generation"],
        help="Research mode preset (default: quick_survey).",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to a custom YAML config file (overrides --preset).",
    )
    parser.add_argument(
        "--api-key", "-k",
        default=None,
        help="DeepSeek API key (or set DEEPSEEK_API_KEY env var).",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress agent interaction logging.",
    )

    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
