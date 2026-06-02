# -*- coding: utf-8 -*-
"""
概念验证：AgentScope v2.0 中实现 v1.0 的 create_worker 动态创建 Agent 模式。

v1.0 的 API (已废弃):               v2.0 的 API (当前):
─────────────────────────          ────────────────────────
ReActAgent(...)                     Agent(...)
toolkit.register_tool_function(fn)  Toolkit(tools=[FunctionTool(func=fn)])
ToolResponse(...)                   ToolChunk(...)
await agent(msg)                    await agent.reply(msg)
sys_prompt                          system_prompt
InMemoryMemory()                    内置于 Agent 上下文

结论：v2.0 没有删除动态创建 Agent 的能力，只是改了 API 名字。
      用 v2.0 API 完全可以实现同样的 create_worker 模式。
"""

import asyncio
import os

from agentscope.agent import Agent
from agentscope.tool import Toolkit, FunctionTool
from agentscope.tool._response import ToolChunk
from agentscope.message import Msg, TextBlock
from agentscope.model import DeepSeekChatModel
from agentscope.credential import DeepSeekCredential


# ============================================================================
# v2.0 版本的 create_worker —— 与 v1.0 功能完全等价
# ============================================================================

async def create_worker(task_description: str) -> ToolChunk:
    """Create a worker agent dynamically to finish the given task.

    This is the v2.0 equivalent of the v1.0 create_worker pattern from
    https://doc.agentscope.io/tutorial/workflow_handoffs.html

    Args:
        task_description: The task for the worker to complete.
    """
    # 给 Worker 配工具（这里以 Python 执行为例，可以换成任何工具）
    worker_toolkit = Toolkit(tools=[])  # 可以加 execute_python_code 等

    # ═══ 核心：在工具函数内部动态 new Agent ═══
    # v1.0: ReActAgent(name="Worker", sys_prompt=..., model=..., formatter=..., toolkit=...)
    # v2.0: Agent(name="Worker", system_prompt=..., model=..., toolkit=...)
    worker = Agent(
        name="Worker",
        system_prompt=(
            "You are a worker agent. Your sole job is to complete "
            "the given task and return the result."
        ),
        model=DeepSeekChatModel(
            credential=DeepSeekCredential(
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            ),
            model="deepseek-chat",
            stream=False,
        ),
        toolkit=worker_toolkit,
    )

    # v1.0: await worker(Msg("user", task_description, "user"))
    # v2.0: await worker.reply(Msg(...))
    result = await worker.reply(
        Msg(name="user", content=task_description, role="user")
    )

    return ToolChunk(content=[TextBlock(text=result.get_text_content())])


# ============================================================================
# 构建 Orchestrator（有 create_worker 工具的主 Agent）
# ============================================================================

def build_orchestrator(api_key: str | None = None) -> Agent:
    """Build an orchestrator agent equipped with the create_worker tool."""
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")

    # 把 create_worker 注册为工具
    toolkit = Toolkit(
        tools=[
            FunctionTool(
                func=create_worker,
                name="create_worker",
                description=(
                    "Create a worker agent dynamically to finish a given task. "
                    "The worker will return the result when done."
                ),
                is_concurrency_safe=True,
                is_read_only=False,  # 会创建新的 Agent 实例
            ),
        ],
    )

    orchestrator = Agent(
        name="Orchestrator",
        system_prompt=(
            "You are an orchestrator agent. To complete the user's task, "
            "decompose it into smaller subtasks and use `create_worker` to "
            "dynamically create workers to handle each subtask. "
            "Collect the results and present the final answer."
        ),
        model=DeepSeekChatModel(
            credential=DeepSeekCredential(api_key=api_key),
            model="deepseek-chat",
            stream=True,
        ),
        toolkit=toolkit,
    )

    return orchestrator


# ============================================================================
# 运行
# ============================================================================

async def main():
    orchestrator = build_orchestrator()

    result = await orchestrator.reply(
        Msg(name="user", content="Execute hello world in Python", role="user")
    )

    print(result.get_text_content())


if __name__ == "__main__":
    asyncio.run(main())
