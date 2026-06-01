# -*- coding: utf-8 -*-
"""Pipeline orchestration strategy — fixed-sequence agent execution.

This is a simpler, predictable strategy where agents are called in a fixed order.
Useful for quick surveys or when you want deterministic behavior.
"""

from __future__ import annotations

import logging
from typing import Optional

from agentscope.message import Msg

from .base import OrchestrationStrategy

logger = logging.getLogger(__name__)


class PipelineStrategy(OrchestrationStrategy):
    """Fixed-sequence pipeline orchestration.

    Agents are called one after another in a predetermined order. Each agent
    receives the previous agent's output as its input. The final agent's
    output is returned.
    """

    def __init__(self, sequence: list[str], verbose: bool = True):
        """Initialize the pipeline strategy.

        Args:
            sequence: Ordered list of agent names to invoke, e.g.
                ["searcher", "analyst", "synthesizer", "ideator", "chief"].
            verbose: Whether to print agent interactions to stdout.
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

        Raises:
            KeyError: If any agent name in the sequence doesn't exist in the team.
        """
        if self.verbose:
            logger.info("=" * 60)
            logger.info(f"Pipeline: {' → '.join(self.sequence)}")
            logger.info(f"Question: {user_msg.get_text_content()[:200]}")
            logger.info("=" * 60)

        current_msg = user_msg

        for i, agent_name in enumerate(self.sequence):
            agent = team.get_agent(agent_name)

            if self.verbose:
                logger.info(
                    f"[Step {i + 1}/{len(self.sequence)}] Running {agent_name}..."
                )

            current_msg = await agent.reply(current_msg)

            preview = current_msg.get_text_content()[:300]
            if len(current_msg.get_text_content()) > 300:
                preview += "..."
            if self.verbose:
                logger.info(f"[{agent_name}]\n{preview}\n")

        if self.verbose:
            logger.info("=" * 60)
            logger.info("Pipeline complete.")
            logger.info("=" * 60)

        return current_msg


# ============================================================================
# Preset pipeline sequences
# ============================================================================

# Quick survey: search → chief synthesizes
QUICK_SURVEY = ["searcher", "chief"]

# Standard analysis: search → analyze → chief
STANDARD_ANALYSIS = ["searcher", "analyst", "chief"]

# Deep dive: search → analyze → synthesize → chief
DEEP_ANALYSIS = ["searcher", "analyst", "synthesizer", "chief"]

# Full idea generation pipeline
IDEA_GENERATION = ["searcher", "analyst", "synthesizer", "ideator", "chief"]


def pipeline_strategy(
    sequence: Optional[list[str]] = None,
    preset: str = "quick_survey",
    verbose: bool = True,
) -> PipelineStrategy:
    """Create a pipeline orchestration strategy.

    Args:
        sequence: Custom agent sequence (overrides preset if provided).
        preset: Preset sequence name — "quick_survey", "standard_analysis",
            "deep_analysis", or "idea_generation".
        verbose: Print agent interactions during execution.

    Returns:
        Configured PipelineStrategy instance.

    Raises:
        ValueError: If the preset name is not recognized.
    """
    presets = {
        "quick_survey": QUICK_SURVEY,
        "standard_analysis": STANDARD_ANALYSIS,
        "deep_analysis": DEEP_ANALYSIS,
        "idea_generation": IDEA_GENERATION,
    }

    if sequence is not None:
        pass  # Use the provided sequence
    elif preset in presets:
        sequence = presets[preset]
    else:
        raise ValueError(
            f"Unknown preset '{preset}'. Available: {list(presets.keys())}"
        )

    return PipelineStrategy(sequence=sequence, verbose=verbose)
