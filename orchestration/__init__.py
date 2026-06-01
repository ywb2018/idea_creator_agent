# -*- coding: utf-8 -*-
"""Orchestration strategies for multi-agent research."""

from .base import OrchestrationStrategy
from .autonomous import AutonomousStrategy, autonomous_strategy
from .pipeline import (
    PipelineStrategy,
    pipeline_strategy,
    QUICK_SURVEY,
    STANDARD_ANALYSIS,
    DEEP_ANALYSIS,
    IDEA_GENERATION,
)
from .router import parse_delegation, has_delegation, extract_all_delegations

__all__ = [
    "OrchestrationStrategy",
    "AutonomousStrategy",
    "autonomous_strategy",
    "PipelineStrategy",
    "pipeline_strategy",
    "QUICK_SURVEY",
    "STANDARD_ANALYSIS",
    "DEEP_ANALYSIS",
    "IDEA_GENERATION",
    "parse_delegation",
    "has_delegation",
    "extract_all_delegations",
]
