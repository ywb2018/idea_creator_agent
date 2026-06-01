# -*- coding: utf-8 -*-
"""Autonomous orchestration strategy — Chief-driven dynamic delegation.

This is the primary "harness" mode. The Chief agent receives the user query,
dynamically decides which specialist to call, and iteratively refines the
research until it produces a final answer.
"""

from __future__ import annotations

import logging
from typing import Optional

from agentscope.message import Msg, TextBlock

from .base import OrchestrationStrategy
from .router import parse_delegation

logger = logging.getLogger(__name__)


class AutonomousStrategy(OrchestrationStrategy):
    """Chief-driven autonomous orchestration.

    The Chief agent acts as an autonomous orchestrator:
    1. Receives the user query
    2. Produces a response — either a DELEGATE TO directive or a final answer
    3. If delegation: route to the named specialist, feed result back to Chief
    4. Repeat until Chief produces a non-delegation response or max_rounds is hit

    This is the most flexible strategy — the Chief can adapt its approach based
    on intermediate results, do multiple rounds of search, skip unnecessary steps,
    etc.
    """

    def __init__(self, max_rounds: int = 15, verbose: bool = True):
        """Initialize the autonomous strategy.

        Args:
            max_rounds: Maximum number of Chief→Specialist→Chief rounds before
                forcing termination.
            verbose: Whether to print agent interactions to stdout.
        """
        self.max_rounds = max_rounds
        self.verbose = verbose

    async def execute(
        self,
        team: "ResearchTeam",
        user_msg: Msg,
    ) -> Msg:
        """Execute autonomous research orchestration.

        Args:
            team: ResearchTeam with all agents initialized.
            user_msg: User's research question.

        Returns:
            The Chief's final response message.
        """
        chief = team.chief

        # Kick off: send user query to Chief
        if self.verbose:
            logger.info("=" * 60)
            logger.info(f"Research: {user_msg.get_text_content()[:200]}")
            logger.info("=" * 60)

        result = await chief.reply(user_msg)
        self._log_round("Chief (initial)", result)

        for round_num in range(1, self.max_rounds + 1):
            # Check for delegation directive
            text = result.get_text_content()
            target_name, task = parse_delegation(text)

            if target_name is None:
                # No delegation → Chief is delivering final answer
                if self.verbose:
                    logger.info("No delegation detected. Chief is done.")
                break

            # Route to the specialist
            try:
                specialist = team.get_agent(target_name)
            except KeyError:
                # Chief referenced an unknown agent — feed error back
                if self.verbose:
                    logger.warning(
                        f"Chief delegated to unknown agent '{target_name}'. "
                        f"Available: {team.list_agents()}"
                    )
                error_msg = Msg(
                    name="system",
                    content=[
                        TextBlock(
                            text=f"ERROR: No agent named '{target_name}' exists. "
                            f"Available agents: {', '.join(team.list_agents())}. "
                            f"Please delegate to one of these agents or provide "
                            f"your final answer directly."
                        )
                    ],
                    role="user",
                )
                result = await chief.reply(error_msg)
                continue

            # Execute the specialist
            if self.verbose:
                logger.info(
                    f"[Round {round_num}] Chief → {target_name} "
                    f"(task: {task[:100]}...)"
                )

            specialist_msg = Msg(
                name="chief",
                content=[TextBlock(text=task)],
                role="user",
            )
            specialist_result = await specialist.reply(specialist_msg)
            self._log_round(target_name, specialist_result)

            # Feed specialist result back to Chief
            chief_msg = Msg(
                name=target_name,
                content=specialist_result.content,
                role="user",
            )
            result = await chief.reply(chief_msg)
            self._log_round(f"Chief (round {round_num})", result)

        else:
            # Hit max_rounds
            if self.verbose:
                logger.warning(
                    f"Hit max_rounds ({self.max_rounds}). Returning last response."
                )

        if self.verbose:
            logger.info("=" * 60)
            logger.info("Research complete.")
            logger.info("=" * 60)

        return result

    def _log_round(self, speaker: str, msg: Msg):
        """Log agent output if verbose mode is on."""
        if not self.verbose:
            return
        preview = msg.get_text_content()[:300]
        if len(msg.get_text_content()) > 300:
            preview += "..."
        logger.info(f"[{speaker}]\n{preview}\n")


# ============================================================================
# Factory function for easy creation
# ============================================================================


def autonomous_strategy(max_rounds: int = 15, verbose: bool = True) -> AutonomousStrategy:
    """Create an autonomous orchestration strategy.

    Args:
        max_rounds: Maximum Chief→Specialist→Chief rounds.
        verbose: Print agent interactions during execution.

    Returns:
        Configured AutonomousStrategy instance.
    """
    return AutonomousStrategy(max_rounds=max_rounds, verbose=verbose)
