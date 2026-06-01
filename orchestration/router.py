# -*- coding: utf-8 -*-
"""Delegation directive parser for agent-to-agent message routing.

The Chief agent uses text directives to delegate work to specialists:
    DELEGATE TO <agent_name>:
    <task description>

This module parses those directives to determine where to route messages.
"""

from __future__ import annotations

import re
from typing import Optional

# ============================================================================
# Delegation pattern
# ============================================================================

# Matches: DELEGATE TO <name>: followed by content until the next
# DELEGATE TO or end of string.
_DELEGATION_RE = re.compile(
    r"DELEGATE\s+TO\s+(\w+)\s*:\s*\n?(.*?)(?=\s*DELEGATE\s+TO\s|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def parse_delegation(text: str) -> tuple[Optional[str], Optional[str]]:
    """Parse a Chief agent's response to extract delegation directives.

    Looks for the first occurrence of:
        DELEGATE TO <agent_name>:
        <task description>

    If multiple delegations exist, only the FIRST one is returned. This
    enforces one-delegation-at-a-time discipline.

    Args:
        text: The text content of an agent's response message.

    Returns:
        A tuple of (agent_name, task_description).
        - If a delegation is found: (name, task) where task is stripped.
        - If no delegation is found: (None, None).

    Examples:
        >>> parse_delegation("DELEGATE TO searcher:\\nQuery: LLM agents\\nMax: 5")
        ('searcher', 'Query: LLM agents\\nMax: 5')

        >>> parse_delegation("Here is the final report on LLM agents...")
        (None, None)
    """
    match = _DELEGATION_RE.search(text)
    if match is None:
        return (None, None)

    agent_name = match.group(1).strip().lower()
    task = match.group(2).strip()
    return (agent_name, task)


def has_delegation(text: str) -> bool:
    """Check if a message text contains any delegation directive.

    Args:
        text: The text content of an agent's response message.

    Returns:
        True if the text contains at least one DELEGATE TO directive.
    """
    return _DELEGATION_RE.search(text) is not None


def extract_all_delegations(text: str) -> list[tuple[str, str]]:
    """Extract ALL delegation directives from a message (for batch routing).

    Args:
        text: The text content of an agent's response message.

    Returns:
        A list of (agent_name, task_description) tuples in order of appearance.
    """
    matches = _DELEGATION_RE.findall(text)
    return [(name.strip().lower(), task.strip()) for name, task in matches]
