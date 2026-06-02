# -*- coding: utf-8 -*-
"""Pydantic models for orchestration configuration."""

from typing import Literal

from pydantic import BaseModel, Field


class OrchestrationConfig(BaseModel):
    """Orchestration strategy configuration."""

    strategy: Literal["autonomous", "pipeline"] = "autonomous"
    max_rounds: int = Field(default=15, ge=1, le=100)
    sequence: list[str] | None = None  # for pipeline
    verbose: bool = True
