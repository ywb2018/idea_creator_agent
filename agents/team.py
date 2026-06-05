# -*- coding: utf-8 -*-
"""ResearchTeam — loads agent definitions from .md files and builds a team."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import yaml

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import DeepSeekCredential
from agentscope.model import DeepSeekChatModel
from agentscope.tool import (
    Toolkit,
    FunctionTool,
    ToolBase,
    TaskCreate,
    TaskList,
)

from ..tools import search_arxiv, get_paper_detail


# ============================================================================
# Tool registry — maps tool name strings to FunctionTool or ToolBase instances
# ============================================================================

TOOL_REGISTRY: dict[str, callable | ToolBase] = {
    "search_arxiv": search_arxiv,
    "get_paper_detail": get_paper_detail,
    "TaskCreate": TaskCreate(),
    "TaskList": TaskList(),
}


def _build_toolkit(tool_names: list[str]) -> Toolkit:
    """Convert a list of tool name strings into a Toolkit instance."""
    tools: list = []
    for name in tool_names:
        if name not in TOOL_REGISTRY:
            raise KeyError(
                f"Unknown tool '{name}'. Available: {list(TOOL_REGISTRY.keys())}"
            )
        entry = TOOL_REGISTRY[name]
        if isinstance(entry, ToolBase):
            tools.append(entry)
        else:
            tools.append(
                FunctionTool(
                    func=entry,
                    name=name,
                    description=entry.__doc__ or f"Tool: {name}",
                    is_concurrency_safe=True,
                    is_read_only=True,
                )
            )
    return Toolkit(tools=tools)


# ============================================================================
# .md agent definition loader
# ============================================================================

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def load_agent_definition(path: str | Path) -> dict:
    """Parse a single agent definition .md file.

    Frontmatter (YAML) contains: name, model, tools, max_iters
    Body (markdown) is used as the system_prompt.

    Args:
        path: Path to a .md file.

    Returns:
        Dict with keys: name, model, tools, max_iters, system_prompt.
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")

    # Parse YAML frontmatter
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError(
            f"{path}: missing YAML frontmatter (--- ... ---)"
        )

    meta = yaml.safe_load(match.group(1))
    body = content[match.end():].strip()

    if not body:
        raise ValueError(f"{path}: system_prompt body is empty")

    return {
        "name": meta.get("name", path.stem),
        "model": meta.get("model", "deepseek-v4-flash"),
        "tools": meta.get("tools", []),
        "max_iters": meta.get("max_iters", 15),
        "system_prompt": body,
    }


def load_agent_definitions(
    directory: str | Path,
    names: list[str] | None = None,
) -> list[dict]:
    """Load all .md agent definitions from a directory.

    Args:
        directory: Path to the definitions directory.
        names: Optional filter — only load agents with these names.

    Returns:
        List of agent definition dicts.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Definitions directory not found: {directory}")

    definitions = []
    for md_file in sorted(directory.glob("*.md")):
        try:
            definition = load_agent_definition(md_file)
            if names is None or definition["name"] in names:
                definitions.append(definition)
        except Exception as e:
            print(f"Warning: skipping {md_file}: {e}")

    if names:
        loaded = {d["name"] for d in definitions}
        missing = set(names) - loaded
        if missing:
            raise ValueError(
                f"Agent(s) not found in definitions: {missing}. "
                f"Available: {loaded}"
            )

    return definitions


# ============================================================================
# ResearchTeam
# ============================================================================

_DEFAULT_DEFINITIONS_DIR = Path(__file__).parent / "definitions"


class ResearchTeam:
    """A container for all agents participating in a research session.

    Agents are defined as .md files in a definitions directory.
    Each .md file's frontmatter specifies name/model/tools/max_iters,
    and the markdown body is the system_prompt.

    Usage:
        # Load all agents from definitions dir
        team = ResearchTeam(api_key="sk-...")

        # Load specific agents only
        team = ResearchTeam(api_key="sk-...", agent_names=["chief", "searcher"])
    """

    def __init__(
        self,
        api_key: str,
        definitions_dir: str | Path | None = None,
        agent_names: list[str] | None = None,
        model_overrides: dict[str, str] | None = None,
        tool_overrides: dict[str, list[str]] | None = None,
        prompt_overrides: dict[str, str] | None = None,
    ):
        """Initialize the research team.

        Args:
            api_key: DeepSeek API key.
            definitions_dir: Path to .md agent definitions directory.
                Defaults to agents/definitions/.
            agent_names: Which agents to include (by name in frontmatter).
                None means all .md files in the directory.
            model_overrides: Override model per agent name.
            tool_overrides: Override tools per agent name.
            prompt_overrides: Override system_prompt per agent name.
        """
        definitions_dir = Path(
            definitions_dir or _DEFAULT_DEFINITIONS_DIR
        )

        model_overrides = model_overrides or {}
        tool_overrides = tool_overrides or {}
        prompt_overrides = prompt_overrides or {}

        # Load definitions from .md files
        definitions = load_agent_definitions(definitions_dir, names=agent_names)

        self.agents: dict[str, Agent] = {}

        for definition in definitions:
            name = definition["name"]
            model_name = model_overrides.get(name, definition["model"])
            tool_names = tool_overrides.get(name, definition["tools"])
            system_prompt = prompt_overrides.get(
                name, definition["system_prompt"]
            )
            max_iters = definition["max_iters"]

            # Build model
            credential = DeepSeekCredential(api_key=api_key)
            model = DeepSeekChatModel(
                credential=credential,
                model=model_name,
                stream=True,
            )

            # Build toolkit
            toolkit = _build_toolkit(tool_names)

            # Build agent
            self.agents[name] = Agent(
                name=name,
                system_prompt=system_prompt,
                model=model,
                toolkit=toolkit,
                react_config=ReActConfig(max_iters=max_iters),
            )

    def get_agent(self, name: str) -> Agent:
        """Get an agent by name."""
        if name not in self.agents:
            raise KeyError(
                f"No agent named '{name}' in this team. "
                f"Available: {list(self.agents.keys())}"
            )
        return self.agents[name]

    @property
    def chief(self) -> Agent:
        """Convenience property to get the chief agent."""
        return self.get_agent("chief")

    def list_agents(self) -> list[str]:
        """Return the list of agent names in this team."""
        return list(self.agents.keys())

    def __repr__(self) -> str:
        roles = ", ".join(self.agents.keys())
        return f"ResearchTeam(agents=[{roles}])"
