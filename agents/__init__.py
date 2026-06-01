# -*- coding: utf-8 -*-
"""Agent definitions, factory, and team container."""

from .factory import build_agent
from .team import ResearchTeam
from .prompts import get_prompt, list_roles, ROLE_PROMPTS

__all__ = [
    "build_agent",
    "ResearchTeam",
    "get_prompt",
    "list_roles",
    "ROLE_PROMPTS",
]
