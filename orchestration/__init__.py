# -*- coding: utf-8 -*-
"""Orchestration strategies for multi-agent research."""

from .base import OrchestrationStrategy
from .autonomous import AutonomousStrategy, autonomous_strategy
from .pipeline import PipelineStrategy, pipeline_strategy
from .router import parse_delegation, has_delegation

__all__ = [
    "OrchestrationStrategy",
    "AutonomousStrategy",
    "autonomous_strategy",
    "PipelineStrategy",
    "pipeline_strategy",
    "parse_delegation",
    "has_delegation",
]
