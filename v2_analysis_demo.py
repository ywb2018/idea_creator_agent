# -*- coding: utf-8 -*-
"""
AgentScope v2.0 动态创建临时 Worker Agent — 带完整源码引用和执行追踪注释。

每个 API 调用都标注了对应的源码文件和行号。
"""
import asyncio
import os
from uuid import uuid4

# ============================================================
# v2.0 API 导入（每个模块标注了源码位置）
# ============================================================

# Agent 类: src/agentscope/agent/_agent.py
#   __init__ → L97-109
#   reply()  → L213-249
#   _reply_impl() → L496-639 (ReAct 循环核心)
#   _reasoning()  → L641+   (调 LLM)
from agentscope.agent import Agent

# Toolkit: src/agentscope/tool/_toolkit.py L66
#   __init__(tools=[...]) → 注册工具到 "basic" 组
from agentscope.tool import Toolkit

# FunctionTool: src/agentscope/tool/_adapters.py L29-118
#   __init__(func, name, description, ...) → L47-82
#   __call__(**kwargs) → L103-118 (最终执行 func(**kwargs))
from agentscope.tool import FunctionTool

# ToolChunk: src/agentscope/tool/_response.py L11-28
#   content: list[TextBlock | DataBlock]
from agentscope.tool._response import ToolChunk

# Msg: src/agentscope/message/_base.py
#   Msg(name, content, role)
# TextBlock: src/agentscope/message/_block.py
#   TextBlock(text)
from agentscope.message import Msg, TextBlock

# DeepSeekChatModel: src/agentscope/model/
#   __init__ → src/agentscope/model/_base.py L56-86
from agentscope.model import DeepSeekChatModel

# DeepSeekCredential: src/agentscope/credential/
from agentscope.credential import DeepSeekCredential


# ============================================================
# 第 1 步：定义 create_worker 工具
#
# 这个函数最终被 FunctionTool 包装，注册到 MainAgent 的 Toolkit。
# 当 MainAgent 的 ReAct 循环走到 [行动阶段]，LLM 要求调用
# create_worker 时，这个函数被执行。
# ============================================================

async def create_worker(task_description: str) -> ToolChunk:
    """Dynamically create a temporary Worker Agent to complete a given task.

    这个函数的执行发生在 MainAgent._reply_impl() 的 [行动阶段] 中
    （_agent.py L577-621）。

    函数内部做了三件事：
      1. 准备 Worker 的工具
      2. 调用 Agent.__init__() 创建 Worker  ← [构建阶段]
      3. 调用 Worker.reply() 执行任务       ← [执行阶段]

    Worker 执行完毕后，函数返回，Worker 对象离开作用域，等待 GC。
    """
    # ─── 1a. 准备 Worker 的工具 ───
    from agentscope.tool import execute_python_code

    # Toolkit.__init__: tool/_toolkit.py L66
    worker_toolkit = Toolkit(
        tools=[
            # FunctionTool.__init__: tool/_adapters.py L47-82
            FunctionTool(
                func=execute_python_code,
                name="execute_python_code",
                description="Execute Python code and return the output.",
                is_concurrency_safe=True,
                is_read_only=False,
            ),
        ],
    )

    # ─── 1b. [构建阶段] 动态创建 Worker Agent ───
    # Agent.__init__: agent/_agent.py L97-109
    # 此时只是 Python 对象构造，无网络请求：
    #   self.name = f"Worker_{...}"
    #   self._system_prompt = "..."
    #   self.model = DeepSeekChatModel 实例
    #   self.state = AgentState()         ← 自动生成唯一 session_id
    #   self.state.context = []           ← 独立上下文，与 MainAgent 隔离
    #   self.toolkit = worker_toolkit
    #   self.react_config = ReActConfig() ← max_iters=10 (默认)
    worker = Agent(
        name=f"Worker_{uuid4().hex[:8]}",
        system_prompt=(
            "You are a worker agent. Complete the given task "
            "and return the result concisely."
        ),
        model=DeepSeekChatModel(
            credential=DeepSeekCredential(
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            ),
            model="deepseek-chat",
            stream=False,  # Worker 用非流式
        ),
        toolkit=worker_toolkit,
    )

    # ─── 1c. [执行阶段] 运行 Worker ───
    # Agent.reply(): agent/_agent.py L213-249
    #   内部调用 _reply() → _reply_impl() (L496)
    #   _reply_impl 内部走完整的 ReAct 循环:
    #
    #   cur_iter=0: [判断] → "reasoning" (第一轮)
    #   cur_iter=0: [推理] → LLM 返回 tool_call: execute_python_code(...)
    #   cur_iter=0: [行动] → 实际执行 print("Hello, World!")
    #   cur_iter=1: [判断] → "reasoning" (队列空)
    #   cur_iter=1: [推理] → LLM: "执行成功，打印了 Hello, World!"
    #                       → 纯文本，无 tool_call
    #   cur_iter=2: [判断] → "exit" (队列空 + 有文本输出)
    #
    #   Worker 的 _reply_impl 返回 final Msg
    result = await worker.reply(
        Msg(name="user", content=task_description, role="user")
    )

    # ─── 1d. 返回结果给 MainAgent ───
    # ToolChunk: tool/_response.py L11-28
    # 这个 ToolChunk 会被 MainAgent 的 [行动阶段] 包装为 ToolResultBlock，
    # 写入 MainAgent.state.context，然后 MainAgent 的 [推理阶段] 读取它
    return ToolChunk(
        content=[TextBlock(text=result.get_text_content())],
    )


# ============================================================
# 第 2 步：构建 MainAgent
#
# MainAgent 是用户直接交互的 Agent。
# 它的 Toolkit 中只有一个工具: create_worker。
# ============================================================

def build_main_agent(api_key: str | None = None) -> Agent:
    """[构建阶段] 创建 MainAgent。

    这个函数中发生的事情:
      1. 把 create_worker 函数包装为 FunctionTool
      2. 注册到 Toolkit
      3. 创建 Agent 实例

    全程无网络请求。
    """
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")

    # Toolkit.__init__: tool/_toolkit.py L66
    # tools=[] 中的工具自动注册到 "basic" 组（默认激活）
    main_toolkit = Toolkit(
        tools=[
            FunctionTool(
                func=create_worker,
                name="create_worker",
                description=(
                    "Create a temporary worker agent to complete a given task. "
                    "The worker can execute Python code."
                ),
                is_concurrency_safe=True,
                is_read_only=False,
            ),
        ],
    )

    # Agent.__init__: agent/_agent.py L97-109
    return Agent(
        name="MainAgent",
        system_prompt=(
            "You are the main agent. Use `create_worker` to dynamically "
            "create temporary worker agents for subtasks."
        ),
        model=DeepSeekChatModel(
            credential=DeepSeekCredential(api_key=api_key),
            model="deepseek-chat",
            stream=True,
        ),
        toolkit=main_toolkit,
    )


# ============================================================
# 第 3 步：运行 — 触发完整执行链路
# ============================================================

async def main():
    # [构建阶段] — 纯 Python 对象创建
    agent = build_main_agent()

    # [执行阶段] — 从这里开始有 LLM 调用
    #
    # agent.reply() → _reply() → _reply_impl() (agent/_agent.py L496)
    #
    # MainAgent 的 ReAct 循环:
    #
    #   cur_iter=0: [判断] → "reasoning"
    #   cur_iter=0: [推理] → LLM: "I'll create a worker to print Hello World"
    #                      → tool_call: create_worker(task_description="Print 'Hello, World!'")
    #
    #   cur_iter=0: [行动] → 执行 create_worker()
    #                      → 内部: Worker [构建] → Worker [执行] → 返回 ToolChunk
    #                      → ⬆ 嵌套的完整 Agent 生命周期 ⬆
    #                      → ToolResultBlock 写入 MainAgent.state.context
    #
    #   cur_iter=1: [判断] → "reasoning"
    #   cur_iter=1: [推理] → LLM: "The worker successfully printed Hello, World!"
    #                      → 纯文本，无 tool_call
    #
    #   cur_iter=2: [判断] → "exit"
    #   → 返回 final Msg
    result = await agent.reply(
        Msg(name="user", content="Print 'Hello, World!' in Python", role="user")
    )

    print("=" * 60)
    print("FINAL RESULT:")
    print(result.get_text_content())


if __name__ == "__main__":
    asyncio.run(main())
