# -*- coding: utf-8 -*-
"""Idea Creator — A harness-based research paper search, analysis, and
idea generation system built on AgentScope v2.0.

Quick start:
    from idea_creator import research

    result = await research(
        "What are recent advances in multi-agent LLM systems?",
    )
    print(result)
"""

# Load .env file before anything else
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

from .agents import ResearchTeam
from .orchestration import (
    AutonomousStrategy,
    PipelineStrategy,
    autonomous_strategy,
    pipeline_strategy,
)
from .config import OrchestrationConfig, load_orchestration_config

__all__ = [
    "ResearchTeam",
    "AutonomousStrategy",
    "PipelineStrategy",
    "autonomous_strategy",
    "pipeline_strategy",
    "OrchestrationConfig",
    "load_orchestration_config",
    "research",
]


async def research(
    query: str,
    agent_names: list[str] | None = None,
    api_key: str | None = None,
    config: str | Path | OrchestrationConfig | None = None,
    strategy: str = "autonomous",
    max_rounds: int = 15,
    verbose: bool = True,
) -> str:
    """Run a research query.

    Args:
        query: The research question or topic.
        agent_names: Which agents to include (defaults to all in definitions/).
        api_key: DeepSeek API key. Falls back to DEEPSEEK_API_KEY env var.
        config: Optional orchestration config — a path to a YAML file, or an
            OrchestrationConfig instance. Overrides strategy/max_rounds/verbose.
        strategy: "autonomous" or "pipeline" (ignored if config is provided).
        max_rounds: Max delegation rounds (ignored if config is provided).
        verbose: Print agent interactions (ignored if config is provided).

    Returns:
        The final research report as a text string.
    """
    import os

    from agentscope.message import Msg, TextBlock

    from .agents import ResearchTeam
    from .orchestration import autonomous_strategy, pipeline_strategy

    # Resolve orchestration config
    if config is not None:
        if isinstance(config, (str, Path)):
            config = load_orchestration_config(config)
        strategy = config.strategy
        max_rounds = config.max_rounds
        verbose = config.verbose
        if config.sequence:
            agent_names = config.sequence

    # Resolve API key
    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError(
                "No API key provided. Set DEEPSEEK_API_KEY in .env or "
                "environment, or pass api_key parameter."
            )

    # Build team from .md definitions
    team = ResearchTeam(
        api_key=api_key,
        agent_names=agent_names,
    )

    # Build strategy
    if strategy == "pipeline":
        strat = pipeline_strategy(
            sequence=agent_names or team.list_agents(),
            verbose=verbose,
        )
    else:
        strat = autonomous_strategy(
            max_rounds=max_rounds,
            verbose=verbose,
        )

    # Execute
    user_msg = Msg(
        name="user",
        content=[TextBlock(text=query)],
        role="user",
    )
    result_msg = await strat.execute(team, user_msg)
    text = result_msg.get_text_content()

    # Save final report to reports/ directory
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = "".join(c if c.isalnum() or c in "_-" else "_" for c in query)[:40]
    report_path = report_dir / f"report_{timestamp}_{safe_query}.md"
    report_path.write_text(text, encoding="utf-8")
    if verbose:
        print(f"\n📄 报告已保存: {report_path.resolve()}", flush=True)

    return text
