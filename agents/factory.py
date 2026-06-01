# -*- coding: utf-8 -*-
"""Agent factory — builds configured Agent instances from role specifications."""

from __future__ import annotations

from typing import Optional

from agentscope.agent import Agent, ReActConfig
from agentscope.model import ChatModelBase
from agentscope.tool import Toolkit

from .prompts import get_prompt


def build_agent(
    name: str,
    role: str,
    model: ChatModelBase,
    toolkit: Toolkit,
    system_prompt: Optional[str] = None,
    max_iters: int = 15,
) -> Agent:
    """Build a single AgentScope Agent configured for a specific role.

    This is the central factory function. Every agent in the system is created
    through this function, ensuring consistent configuration patterns.

    Args:
        name: Unique name for this agent instance (e.g. "chief", "searcher").
        role: The agent's role — determines the default system prompt.
              One of: "chief", "searcher", "analyst", "synthesizer", "ideator".
        model: A configured ChatModelBase instance (e.g. DeepSeekChatModel).
        toolkit: A Toolkit instance with the tools this agent can use.
        system_prompt: Optional override for the default role prompt.
        max_iters: Maximum reasoning-acting iterations for the ReAct loop.

    Returns:
        A fully configured AgentScope Agent ready for use.

    Raises:
        KeyError: If the role is not recognized and no system_prompt is provided.
    """
    if system_prompt is None:
        system_prompt = get_prompt(role)

    return Agent(
        name=name,
        system_prompt=system_prompt,
        model=model,
        toolkit=toolkit,
        react_config=ReActConfig(max_iters=max_iters),
    )
