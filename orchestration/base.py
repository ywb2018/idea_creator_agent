# -*- coding: utf-8 -*-
"""Abstract base for orchestration strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentscope.message import Msg


class OrchestrationStrategy(ABC):
    """Abstract base class for all orchestration strategies.

    An orchestration strategy defines *how* agents in a ResearchTeam interact.
    Different strategies can drive the same team in different ways:

    - AutonomousStrategy: Chief dynamically decides whom to call.
    - PipelineStrategy: Fixed sequence of agent invocations.

    This is the core of the "harness" design — swap the strategy without
    modifying the agents themselves.
    """

    @abstractmethod
    async def execute(self, team: "ResearchTeam", user_msg: Msg) -> Msg:
        """Execute the research process.

        Args:
            team: A ResearchTeam instance with initialized agents.
            user_msg: The user's research question as a Msg.

        Returns:
            The final response Msg from the research process.
        """
        ...
