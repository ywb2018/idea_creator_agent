# -*- coding: utf-8 -*-
"""Configuration loading utilities."""

from pathlib import Path

import yaml

from .models import OrchestrationConfig


def load_orchestration_config(path: str | Path) -> OrchestrationConfig:
    """Load orchestration config from a YAML file.

    Args:
        path: Path to a YAML config file.

    Returns:
        Validated OrchestrationConfig.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return OrchestrationConfig(**data)
