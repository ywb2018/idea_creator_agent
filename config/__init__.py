# -*- coding: utf-8 -*-
"""Configuration system for research modes."""

from .models import ResearchModeConfig, AgentSpec, OrchestrationSpec
from .loader import load_config, load_preset, list_presets, create_config

__all__ = [
    "ResearchModeConfig",
    "AgentSpec",
    "OrchestrationSpec",
    "load_config",
    "load_preset",
    "list_presets",
    "create_config",
]
