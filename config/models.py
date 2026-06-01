# -*- coding: utf-8 -*-
"""Pydantic models for configuration validation."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AgentSpec(BaseModel):
    """Specification for a single agent in a research team.

    Each AgentSpec defines one agent's role, model, tools, and behavioral
    overrides. Multiple AgentSpecs together define the team composition.
    """

    name: str = Field(description="Unique name for this agent instance.")
    role: Literal["chief", "searcher", "analyst", "synthesizer", "ideator"] = Field(
        description="The agent's role — determines its system prompt and defaults."
    )
    model: str = Field(
        default="deepseek-chat",
        description="Model identifier, e.g. 'deepseek-chat' or 'deepseek-reasoner'.",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="List of tool names to register with this agent. "
        "Available: search_arxiv, get_paper_detail.",
    )
    system_prompt_override: Optional[str] = Field(
        default=None,
        description="Optional custom system prompt to replace the role default.",
    )
    max_iters: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Maximum ReAct loop iterations for this agent.",
    )


class OrchestrationSpec(BaseModel):
    """Specification for the orchestration strategy."""

    strategy: Literal["autonomous", "pipeline"] = Field(
        default="autonomous",
        description="Orchestration strategy: 'autonomous' (Chief-driven) or "
        "'pipeline' (fixed sequence).",
    )
    max_rounds: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Maximum Chief→Specialist→Chief rounds (autonomous only).",
    )
    sequence: Optional[list[str]] = Field(
        default=None,
        description="Ordered list of agent names for pipeline strategy.",
    )
    verbose: bool = Field(
        default=True,
        description="Whether to print agent interactions during execution.",
    )


class ResearchModeConfig(BaseModel):
    """Top-level configuration for a research mode.

    A ResearchModeConfig fully describes a research setup: what agents to create,
    what models they use, what tools they have, and how they coordinate.

    This is the primary configuration unit — users select a preset mode or write
    a custom one.
    """

    name: str = Field(description="Display name for this research mode.")
    description: str = Field(
        description="Human-readable description of what this mode does."
    )
    orchestration: OrchestrationSpec = Field(
        default_factory=OrchestrationSpec,
        description="How agents should coordinate.",
    )
    agents: list[AgentSpec] = Field(
        description="Agent definitions for the research team.",
    )

    # For YAML convenience: allow model defaults
    model_defaults: dict[str, str] = Field(
        default_factory=dict,
        description="Default model names keyed by role, e.g. "
        "{'chief': 'deepseek-reasoner', 'searcher': 'deepseek-chat'}.",
    )
