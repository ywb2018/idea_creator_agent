# -*- coding: utf-8 -*-
"""Configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from .models import ResearchModeConfig

# Directory where preset YAML files live
_PRESETS_DIR = Path(__file__).parent / "presets"


def load_config(path: str | Path) -> ResearchModeConfig:
    """Load and validate a research mode configuration from a YAML file.

    Args:
        path: Path to a YAML configuration file.

    Returns:
        A validated ResearchModeConfig instance.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        pydantic.ValidationError: If the config is invalid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return ResearchModeConfig(**data)


def load_preset(name: str) -> ResearchModeConfig:
    """Load a built-in preset by name.

    Args:
        name: Preset name (without .yaml extension), e.g. "quick_survey"
            or "idea_generation".

    Returns:
        A validated ResearchModeConfig instance.

    Raises:
        FileNotFoundError: If the preset doesn't exist.
        pydantic.ValidationError: If the preset config is invalid.
    """
    preset_path = _PRESETS_DIR / f"{name}.yaml"
    return load_config(preset_path)


def list_presets() -> list[str]:
    """List all available preset names.

    Returns:
        List of preset names (without .yaml extension).
    """
    if not _PRESETS_DIR.exists():
        return []
    return sorted(
        p.stem for p in _PRESETS_DIR.glob("*.yaml")
    )


def create_config(
    name: str,
    description: str = "",
    strategy: str = "autonomous",
    agents: Optional[list[dict]] = None,
    max_rounds: int = 15,
    sequence: Optional[list[str]] = None,
    verbose: bool = True,
    model_defaults: Optional[dict[str, str]] = None,
) -> ResearchModeConfig:
    """Programmatically create a ResearchModeConfig without a YAML file.

    This is the programmatic API for building configurations. Useful when
    you want to dynamically construct a team in code rather than loading
    a preset file.

    Args:
        name: Display name for this mode.
        description: Human-readable description.
        strategy: "autonomous" or "pipeline".
        agents: List of agent spec dicts. Each dict should have keys:
            name, role, and optionally model, tools, max_iters.
        max_rounds: Max rounds for autonomous strategy.
        sequence: Agent sequence for pipeline strategy.
        verbose: Print agent interactions.
        model_defaults: Default model per role.

    Returns:
        A validated ResearchModeConfig.
    """
    from .models import AgentSpec, OrchestrationSpec

    agent_specs = []
    for a in (agents or []):
        agent_specs.append(AgentSpec(**a))

    orch_spec = OrchestrationSpec(
        strategy=strategy,
        max_rounds=max_rounds,
        sequence=sequence,
        verbose=verbose,
    )

    return ResearchModeConfig(
        name=name,
        description=description,
        orchestration=orch_spec,
        agents=agent_specs,
        model_defaults=model_defaults or {},
    )
