# -*- coding: utf-8 -*-
"""ResearchTeam — a container that holds all agents for a research session."""

from __future__ import annotations

from typing import Optional

from agentscope.agent import Agent
from agentscope.model import ChatModelBase
from agentscope.tool import Toolkit, FunctionTool

from .factory import build_agent
from ..tools import search_arxiv, get_paper_detail

# ============================================================================
# Tool assignment: which roles get which tools by default
# ============================================================================

DEFAULT_TOOL_SETS: dict[str, list] = {
    "chief": [],  # Chief delegates only — no tools needed
    "searcher": ["search_arxiv", "get_paper_detail"],
    "analyst": ["get_paper_detail"],
    "synthesizer": ["search_arxiv"],
    "ideator": ["search_arxiv"],
}

# Mapping of tool names to actual functions
TOOL_REGISTRY: dict[str, callable] = {
    "search_arxiv": search_arxiv,
    "get_paper_detail": get_paper_detail,
}


def _build_toolkit(tool_names: list[str]) -> Toolkit:
    """Build a Toolkit from a list of tool function names.

    Args:
        tool_names: List of tool names (must be keys in TOOL_REGISTRY).

    Returns:
        A Toolkit with the requested tools registered as FunctionTool instances.
    """
    tools = []
    for name in tool_names:
        if name not in TOOL_REGISTRY:
            raise KeyError(
                f"Unknown tool '{name}'. Available: {list(TOOL_REGISTRY.keys())}"
            )
        func = TOOL_REGISTRY[name]
        tools.append(
            FunctionTool(
                func=func,
                name=name,
                description=func.__doc__ or f"Tool: {name}",
                is_concurrency_safe=True,
                is_read_only=True,
            )
        )
    return Toolkit(tools=tools)


class ResearchTeam:
    """A container for all agents participating in a research session.

    The ResearchTeam is the central "harness" — it holds the agents, but does NOT
    control how they interact. Orchestration is handled by a separate
    OrchestrationStrategy, making the team composable and strategy-swappable.

    Usage:
        team = ResearchTeam(api_key="sk-...")
        # Or with custom models per agent:
        team = ResearchTeam(
            api_key="sk-...",
            model_overrides={"chief": "deepseek-reasoner", "searcher": "deepseek-chat"},
        )
    """

    def __init__(
        self,
        api_key: str,
        model_class: Optional[type] = None,
        model_overrides: Optional[dict[str, str]] = None,
        tool_overrides: Optional[dict[str, list[str]]] = None,
        prompt_overrides: Optional[dict[str, str]] = None,
        roles: Optional[list[str]] = None,
    ):
        """Initialize the research team.

        Args:
            api_key: API key for the model provider.
            model_class: Model class to use (defaults to DeepSeekChatModel).
            model_overrides: Per-agent model name overrides, e.g.
                {"chief": "deepseek-reasoner"}.
            tool_overrides: Per-agent tool list overrides.
            prompt_overrides: Per-agent system prompt overrides.
            roles: Which roles to instantiate (defaults to all 5).
        """
        self.api_key = api_key
        self.roles = roles or list(DEFAULT_TOOL_SETS.keys())

        # Resolve model class
        if model_class is None:
            from agentscope.model import DeepSeekChatModel

            model_class = DeepSeekChatModel

        # Resolve overrides
        model_overrides = model_overrides or {}
        tool_overrides = tool_overrides or {}
        prompt_overrides = prompt_overrides or {}

        # Build all agents
        self.agents: dict[str, Agent] = {}
        for role in self.roles:
            model_name = model_overrides.get(role, "deepseek-chat")
            tool_names = tool_overrides.get(role, DEFAULT_TOOL_SETS.get(role, []))
            system_prompt = prompt_overrides.get(role, None)

            # Create credential and model
            from agentscope.credential import DeepSeekCredential

            credential = DeepSeekCredential(api_key=api_key)
            model = model_class(
                credential=credential,
                model=model_name,
                stream=True,
            )

            # Create toolkit
            toolkit = _build_toolkit(tool_names)

            # Build agent
            agent = build_agent(
                name=role,
                role=role,
                model=model,
                toolkit=toolkit,
                system_prompt=system_prompt,
            )
            self.agents[role] = agent

    def get_agent(self, name: str) -> Agent:
        """Get an agent by name.

        Args:
            name: The agent's name (e.g. "chief", "searcher").

        Returns:
            The Agent instance.

        Raises:
            KeyError: If no agent with that name exists in the team.
        """
        if name not in self.agents:
            raise KeyError(
                f"No agent named '{name}' in this team. "
                f"Available: {list(self.agents.keys())}"
            )
        return self.agents[name]

    @property
    def chief(self) -> Agent:
        """Convenience property to get the chief agent."""
        return self.get_agent("chief")

    def list_agents(self) -> list[str]:
        """Return the list of agent names in this team."""
        return list(self.agents.keys())

    def __repr__(self) -> str:
        roles = ", ".join(self.agents.keys())
        return f"ResearchTeam(agents=[{roles}])"
