# -*- coding: utf-8 -*-
"""Idea Creator — A harness-based research paper search, analysis, and
idea generation system built on AgentScope.

Quick start:
    from idea_creator import research

    result = await research(
        "What are recent advances in multi-agent LLM systems?",
        preset="quick_survey",
        api_key="sk-...",
    )
    print(result)
"""

from .agents import ResearchTeam, build_agent, get_prompt, list_roles
from .orchestration import (
    AutonomousStrategy,
    PipelineStrategy,
    autonomous_strategy,
    pipeline_strategy,
)
from .config import (
    ResearchModeConfig,
    AgentSpec,
    OrchestrationSpec,
    load_config,
    load_preset,
    list_presets,
    create_config,
)

# Lazy import for the main entry point — avoids circular deps
__all__ = [
    # Agents
    "ResearchTeam",
    "build_agent",
    "get_prompt",
    "list_roles",
    # Orchestration
    "AutonomousStrategy",
    "PipelineStrategy",
    "autonomous_strategy",
    "pipeline_strategy",
    # Config
    "ResearchModeConfig",
    "AgentSpec",
    "OrchestrationSpec",
    "load_config",
    "load_preset",
    "list_presets",
    "create_config",
    # Entry point
    "research",
]


async def research(
    query: str,
    preset: str = "quick_survey",
    config_path: str | None = None,
    api_key: str | None = None,
    verbose: bool = True,
) -> str:
    """Run a research query with a single function call.

    This is the simplest programmatic API. It loads a preset (or custom config),
    builds the team, and executes the research.

    Args:
        query: The research question or topic.
        preset: Name of a built-in preset ("quick_survey", "idea_generation").
            Ignored if config_path is provided.
        config_path: Path to a custom YAML config file.
        api_key: DeepSeek API key. Falls back to DEEPSEEK_API_KEY env var.
        verbose: Print agent interactions to stdout.

    Returns:
        The final research report / ideas as a text string.

    Raises:
        FileNotFoundError: If the preset or config_path doesn't exist.
        ValueError: If API key is not provided and not in environment.
    """
    import os

    from .agents import ResearchTeam
    from .orchestration import autonomous_strategy, pipeline_strategy

    # Resolve config
    if config_path:
        from .config import load_config

        config = load_config(config_path)
    else:
        from .config import load_preset

        config = load_preset(preset)

    # Resolve API key
    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError(
                "No API key provided. Set DEEPSEEK_API_KEY environment variable "
                "or pass api_key parameter."
            )

    # Build model overrides from config
    model_overrides = config.model_defaults or {}
    tool_overrides = {}
    prompt_overrides = {}
    for agent_spec in config.agents:
        if agent_spec.model:
            model_overrides[agent_spec.name] = agent_spec.model
        tool_overrides[agent_spec.name] = agent_spec.tools
        if agent_spec.system_prompt_override:
            prompt_overrides[agent_spec.name] = agent_spec.system_prompt_override

    roles = [a.name for a in config.agents]

    # Resolve model class
    from agentscope.model import DeepSeekChatModel

    model_class = DeepSeekChatModel

    # Build team
    team = ResearchTeam(
        api_key=api_key,
        model_class=model_class,
        model_overrides=model_overrides,
        tool_overrides=tool_overrides,
        prompt_overrides=prompt_overrides,
        roles=roles,
    )

    # Build strategy
    strat_spec = config.orchestration
    if strat_spec.strategy == "pipeline" and strat_spec.sequence:
        strategy = pipeline_strategy(
            sequence=strat_spec.sequence,
            verbose=strat_spec.verbose,
        )
    else:
        strategy = autonomous_strategy(
            max_rounds=strat_spec.max_rounds,
            verbose=strat_spec.verbose,
        )

    # Execute
    from agentscope.message import Msg, TextBlock

    user_msg = Msg(
        name="user",
        content=[TextBlock(text=query)],
        role="user",
    )
    result_msg = await strategy.execute(team, user_msg)
    return result_msg.get_text_content()
