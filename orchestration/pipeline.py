# -*- coding: utf-8 -*-
"""Pipeline orchestration strategy — fixed-sequence agent execution."""

from __future__ import annotations

from typing import Optional

from agentscope.message import Msg

from .base import OrchestrationStrategy


def _log(*args, **kwargs):
    """Print verbose output immediately (unbuffered)."""
    print(*args, **kwargs, flush=True)


class PipelineStrategy(OrchestrationStrategy):
    """Fixed-sequence pipeline orchestration.

    Agents are called one after another in a predetermined order. Each agent
    receives the previous agent's output as its input.
    """

    def __init__(self, sequence: list[str], verbose: bool = True):
        """Initialize the pipeline strategy.

        Args:
            sequence: Ordered list of agent names to invoke.
            verbose: Whether to print agent interactions.
        """
        self.sequence = sequence
        self.verbose = verbose

    async def execute(
        self,
        team: "ResearchTeam",
        user_msg: Msg,
    ) -> Msg:
        """Execute the pipeline.

        Args:
            team: ResearchTeam with all agents initialized.
            user_msg: User's research question.

        Returns:
            The final agent's response message.
        """
        if self.verbose:
            _log("=" * 60)
            _log(f"Pipeline: {' → '.join(self.sequence)}")
            _log(f"Question: {user_msg.get_text_content()[:200]}")
            _log("=" * 60)

        current_msg = user_msg

        for i, agent_name in enumerate(self.sequence):
            agent = team.get_agent(agent_name)

            if self.verbose:
                _log(
                    f"[Step {i + 1}/{len(self.sequence)}] Running {agent_name}..."
                )

            current_msg = await agent.reply(current_msg)

            preview = current_msg.get_text_content()[:300]
            if len(current_msg.get_text_content()) > 300:
                preview += "..."
            if self.verbose:
                _log(f"[{agent_name}]\n{preview}\n")

        if self.verbose:
            _log("=" * 60)
            _log("Pipeline complete.")
            _log("=" * 60)

        return current_msg


def pipeline_strategy(
    sequence: list[str],
    verbose: bool = True,
) -> PipelineStrategy:
    """Create a pipeline orchestration strategy.

    Args:
        sequence: Ordered list of agent names, e.g. ["searcher", "chief"].
        verbose: Print agent interactions during execution.

    Returns:
        Configured PipelineStrategy instance.
    """
    return PipelineStrategy(sequence=sequence, verbose=verbose)
