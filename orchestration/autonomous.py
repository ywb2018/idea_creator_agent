# -*- coding: utf-8 -*-
"""Autonomous orchestration strategy — Chief-driven dynamic delegation.

This is the primary "harness" mode. The Chief agent receives the user query,
dynamically decides which specialist to call, and iteratively refines the
research until it produces a final answer.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

from agentscope.agent import Agent
from agentscope.event import (
    ExceedMaxItersEvent,
    RequireUserConfirmEvent,
    RequireExternalExecutionEvent,
    ThinkingBlockStartEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
)
from agentscope.message import Msg, TextBlock

from .base import OrchestrationStrategy
from .router import parse_delegation


def _log(*args, **kwargs):
    """Print verbose output immediately (unbuffered)."""
    print(*args, **kwargs, flush=True)


async def _run_agent(agent: Agent, inputs: Msg, tag: str) -> Msg:
    """Run an agent and log its internal events (tool calls, thinking, etc.).

    This gives visibility into the agent's ReAct loop — showing which tools
    are called, when the agent is thinking, and if it hits iteration limits.

    Args:
        agent: The AgentScope agent to run.
        inputs: The input message.
        tag: Log prefix tag (e.g. "searcher", "chief").

    Returns:
        The agent's final reply Msg.
    """
    final_msg: Msg | None = None
    tool_names: dict[str, str] = {}  # tool_call_id → name
    async for evt in agent._reply(inputs=inputs):
        if isinstance(evt, ToolCallStartEvent):
            tool_names[evt.tool_call_id] = evt.tool_call_name
            _log(f"[{tag}] 🔧 调用工具: {evt.tool_call_name}")
        elif isinstance(evt, ToolCallEndEvent):
            name = tool_names.get(evt.tool_call_id, "?")
            _log(f"[{tag}] 🔧 工具返回: {name}")
        elif isinstance(evt, ThinkingBlockStartEvent):
            _log(f"[{tag}] 💭 思考中...")
        elif isinstance(evt, ExceedMaxItersEvent):
            _log(f"[{tag}] ⚠️ 达到最大迭代次数! (agent: {evt.name})")
        elif isinstance(evt, RequireUserConfirmEvent):
            _log(f"[{tag}] ❌ 权限: 工具调用需要用户确认 — 不应该出现!")
        elif isinstance(evt, RequireExternalExecutionEvent):
            _log(f"[{tag}] ❌ 权限: 工具调用需要外部执行 — 不应该出现!")
        elif isinstance(evt, Msg):
            final_msg = evt
    if final_msg is None:
        # Fallback: shouldn't happen but handle gracefully
        return Msg(name=agent.name, content=[TextBlock(text="")], role="assistant")
    return final_msg


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

        # Prepend current timestamp so agents search for recent papers
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        timestamped_text = (
            f"【当前时间: {now}】请基于这个时间进行搜索，优先查找近期的论文和进展。"
            f"\n\n{user_msg.get_text_content()}"
        )
        user_msg = Msg(
            name="user",
            content=[TextBlock(text=timestamped_text)],
            role="user",
        )

        # Kick off: send user query to Chief
        if self.verbose:
            _log("┌" + "─" * 58)
            _log(f"│ 🕐 {now}")
            _log(f"│ 📋 用户提问: {user_msg.get_text_content()[len(timestamped_text)-len(user_msg.get_text_content()):][:100]}")
            _log("└" + "─" * 58)

        result = await _run_agent(chief, user_msg, "chief")
        self._log_round("chief", result)

        for round_num in range(1, self.max_rounds + 1):
            # Check for delegation directive
            text = result.get_text_content()
            target_name, task = parse_delegation(text)

            if target_name is None:
                # No delegation → Chief is delivering final answer
                if self.verbose:
                    _log(f"[chief] ✅ 完成，输出最终报告")
                break

            # Route to the specialist
            try:
                specialist = team.get_agent(target_name)
            except KeyError:
                # Chief referenced an unknown agent — feed error back
                if self.verbose:
                    _log(
                        f"[chief] ⚠️ 委派给未知 agent '{target_name}'，"
                        f"可用: {team.list_agents()}"
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
                result = await _run_agent(chief, error_msg, "chief")
                continue

            # Execute the specialist
            if self.verbose:
                _log(f"[chief → {target_name}] 📤 委派任务 (round {round_num}): "
                     f"{task[:120]}")

            # Inject current time so searcher knows which years to filter for
            time_ctx = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
            specialist_msg = Msg(
                name="chief",
                content=[TextBlock(text=f"【当前时间: {time_ctx}】搜论文和过滤年份时请基于这个时间。\n\n{task}")],
                role="user",
            )
            specialist_result = await _run_agent(specialist, specialist_msg, target_name)
            self._log_round(target_name, specialist_result)

            # Feed specialist result back to Chief
            chief_msg = Msg(
                name=target_name,
                content=specialist_result.content,
                role="user",
            )
            result = await _run_agent(chief, chief_msg, "chief")
            self._log_round("chief", result)

        else:
            # Hit max_rounds
            if self.verbose:
                _log(f"[chief] ⚠️ 达到最大轮次 ({self.max_rounds})，返回最后结果")

        if self.verbose:
            _log("")
            _log(f"[chief] 🏁 研究完成 — 最终报告:")
            _log("─" * 60)

        return result

    def _log_round(self, speaker: str, msg: Msg):
        """Log agent output, prefixing every line with the agent tag.

        Task-related lines (containing 📋 or checkbox markers) get a distinct
        visual prefix so they stand out from regular agent output.
        """
        if not self.verbose:
            return
        text = msg.get_text_content()
        lines = text.split("\n")
        # Show up to 20 lines per round to avoid flooding
        shown = lines[:20]
        if len(lines) > 20:
            shown.append(f"... (省略 {len(lines) - 20} 行)")
        for line in shown:
            # Task list lines get a special 🗂️ prefix
            if any(marker in line for marker in ("📋", "[✓]", "[ ]", "[→]", "Task", "✅")):
                _log(f"[{speaker}] 🗂️  {line}")
            else:
                _log(f"[{speaker}] {line}")
        _log("")  # blank line separator


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
