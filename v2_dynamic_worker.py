# -*- coding: utf-8 -*-
"""
AgentScope v2.0 动态创建临时 Worker Agent —— 完整示例。

使用的全部是 v2.0 API（来自 E:\project\agentscope\src\agentscope\）:

  Agent(name, system_prompt, model, toolkit)    ← agent/_agent.py
  Toolkit(tools=[...])                           ← tool/_toolkit.py
  FunctionTool(func=fn, name=..., description=...) ← tool/_adapters.py
  ToolChunk(content=[TextBlock(text=...)])       ← tool/_response.py
  Msg(name, content, role)                       ← message/_base.py
  TextBlock(text)                                ← message/_block.py
  DeepSeekChatModel(credential, model, stream)    ← model/
  DeepSeekCredential(api_key)                    ← credential/
"""

import asyncio
import os
from uuid import uuid4

# ============================================================
# v2.0 imports — all from src/agentscope/
# ============================================================
from agentscope.agent import Agent                    # _agent.py:97
from agentscope.tool import Toolkit, FunctionTool     # _toolkit.py:66, _adapters.py:29
from agentscope.tool._response import ToolChunk       # _response.py:11
from agentscope.message import Msg, TextBlock         # _base.py, _block.py
from agentscope.model import DeepSeekChatModel         # model/
from agentscope.credential import DeepSeekCredential   # credential/


# ============================================================
# 第 1 步：定义 create_worker 工具函数
# ============================================================

async def create_worker(task_description: str) -> ToolChunk:
    """Dynamically create a temporary Worker Agent to complete a given task.

    This function is wrapped as a FunctionTool and given to the Main Agent.
    When the Main Agent calls this tool, a new Agent is created on the fly,
    executes the task, and returns the result.

    Args:
        task_description: The task for the worker to complete.
    """
    # ── 1a. 给 Worker 准备工具 ──
    # 这里以 Python 代码执行为例，实际可以换成任何 v2.0 工具
    from agentscope.tool import execute_python_code

    worker_toolkit = Toolkit(
        tools=[
            FunctionTool(
                func=execute_python_code,
                name="execute_python_code",
                description="Execute Python code and return the output.",
                is_concurrency_safe=True,
                is_read_only=False,
            ),
        ],
    )

    # ── 1b. 动态创建 Agent ──
    # Agent.__init__ 签名 (agent/_agent.py:97-109):
    #   name, system_prompt, model  ← 必填
    #   toolkit, middlewares, state, offloader, model_config,
    #   context_config, react_config ← 都有默认值
    worker = Agent(
        name=f"Worker_{uuid4().hex[:8]}",        # 唯一名字
        system_prompt=(
            "You are a worker agent. Complete the given task "
            "and return the result concisely."
        ),
        model=DeepSeekChatModel(
            credential=DeepSeekCredential(
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            ),
            model="deepseek-chat",
            stream=False,       # Worker 用非流式，简化处理
        ),
        toolkit=worker_toolkit,
    )

    # ── 1c. 执行 Worker ──
    # agent.reply() 签名 (agent/_agent.py:213-249):
    #   接收 Msg | list[Msg] | None，返回 Msg
    #   内部走完整的 ReAct 循环 (_reply_impl, agent/_agent.py:496)
    result = await worker.reply(
        Msg(name="user", content=task_description, role="user")
    )

    # ── 1d. 返回结果 ──
    # ToolChunk 签名 (tool/_response.py:11-28):
    #   content: list[TextBlock | DataBlock]
    #   state: ToolResultState (默认 RUNNING)
    #   metadata: dict
    return ToolChunk(
        content=[TextBlock(text=result.get_text_content())],
    )


# ============================================================
# 第 2 步：构建 Main Agent，把 create_worker 注册为它的工具
# ============================================================

def build_main_agent(api_key: str | None = None) -> Agent:
    """构建 Main Agent（Orchestrator），配备 create_worker 工具。"""
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")

    # 把 create_worker 函数包装为 FunctionTool
    # FunctionTool.__init__ 签名 (tool/_adapters.py:47-55):
    #   func, name, description, is_concurrency_safe, is_read_only, is_state_injected
    main_toolkit = Toolkit(
        tools=[
            FunctionTool(
                func=create_worker,
                name="create_worker",
                description=(
                    "Create a temporary worker agent to complete a given task. "
                    "The worker can execute Python code. "
                    "Use this when you need to delegate work."
                ),
                is_concurrency_safe=True,
                is_read_only=False,
            ),
        ],
    )

    # Agent.__init__ (agent/_agent.py:97-109)
    main_agent = Agent(
        name="MainAgent",
        system_prompt=(
            "You are the main agent. To complete the user's task, "
            "use the `create_worker` tool to dynamically create "
            "temporary worker agents. Each worker can execute "
            "Python code. Delegate subtasks to workers and "
            "synthesize their results."
        ),
        model=DeepSeekChatModel(
            credential=DeepSeekCredential(api_key=api_key),
            model="deepseek-chat",
            stream=True,
        ),
        toolkit=main_toolkit,
    )

    return main_agent


# ============================================================
# 第 3 步：运行
# ============================================================

async def main():
    agent = build_main_agent()

    # agent.reply() 入口 (agent/_agent.py:213)
    result = await agent.reply(
        Msg(name="user", content="Print 'Hello, World!' in Python", role="user")
    )

    print("=" * 60)
    print("FINAL RESULT:")
    print(result.get_text_content())


if __name__ == "__main__":
    asyncio.run(main())
