# Idea Creator

基于 [AgentScope](https://github.com/agentscope-ai/agentscope) v2.0 构建的**多 Agent 论文检索、分析与创意生成系统**。

## 快速开始

### 安装

```bash
pip install agentscope httpx pyyaml pydantic python-dotenv
```

### 配置

```bash
cp .env.example .env
# 编辑 .env 填入 DeepSeek API Key
```

### 运行

```bash
# 快速综述（2 agent）
python main.py "recent advances in multi-agent LLM systems" --preset quick_survey

# 完整创意生成（5 agent）
python main.py "open problems in mechanistic interpretability" --preset idea_generation
```

```python
# 编程调用
from idea_creator import research
result = await research("LLM agents for code generation", preset="idea_generation")
```

---

## 设计架构

### 整体架构：三层解耦

```
┌─────────────────────────────────────────────────────────┐
│  Config Layer  — 声明式（YAML + Pydantic）               │
│                                                         │
│  定义: 有几个 Agent、各自用什么 model、配什么 tool、      │
│        采用什么 orchestration 策略                       │
├─────────────────────────────────────────────────────────┤
│  Agent Layer   — 能力层（Factory + ResearchTeam）        │
│                                                         │
│  每个 Agent = v2.0 Agent 实例，独立 model + toolkit +    │
│  system_prompt。Agent 之间平级，互不感知                   │
├─────────────────────────────────────────────────────────┤
│  Orchestration Layer — 行为层（Strategy Pattern）        │
│                                                         │
│  可替换的策略接口，定义 Agent 之间如何交互                 │
│    - AutonomousStrategy: Chief 文本委派 + 路由循环       │
│    - PipelineStrategy: 固定序列执行                      │
└─────────────────────────────────────────────────────────┘
```

### Agent 角色

| 角色 | 职责 | 工具 | 思考方式 |
|------|------|------|---------|
| **Chief** | 理解意图、委派任务、合成报告 | TaskCreate, TaskList | "用户要什么？现在该干什么？信息够了吗？" |
| **Searcher** | 检索论文 | search_arxiv, get_paper_detail | "怎么构造查询？哪些结果最相关？" |
| **Analyst** | 单篇深度分析 | get_paper_detail | "这篇论文的方法有什么优点和缺陷？" |
| **Synthesizer** | 多篇横向综合 | search_arxiv | "这些论文之间有什么关系？哪里还有空白？" |
| **Ideator** | 生成研究创意 | search_arxiv | "基于这些 gap，有什么值得做的方向？" |

### 协作流程

```
User: "这个方向有什么 open problems?"

Chief (推理): "拆成 3 步: 搜索→分析→创意生成"
  │
  ├─ DELEGATE TO searcher: 搜索近期 survey
  │     └─ Searcher 返回 5 篇论文
  │
  ├─ DELEGATE TO analyst: 分析最相关的 3 篇
  │     └─ Analyst 返回结构化批判分析
  │
  ├─ DELEGATE TO synthesizer: 横向对比，找 gap
  │     └─ Synthesizer 返回趋势 + 空白点
  │
  ├─ DELEGATE TO ideator: 基于 gap 生成 3 个 idea
  │     └─ Ideator 返回结构化创意
  │
  └─ Chief 合成最终报告 → 返回给 User
```

### 两种编排策略

**Autonomous（默认）**：Chief 动态决策，根据中间结果自适应调整。可以重复搜索、跳过不必要的步骤、深入感兴趣的方向。`max_rounds` 防止无限循环。

**Pipeline**：固定序列执行，可预测、速度快。适合明确的线性场景（如 `quick_survey`）。

### 委派机制

Chief 通过 LLM 输出文本指令 `DELEGATE TO <agent_name>:` 来委派任务。Orchestration 层的 Router 用正则解析指令，找到对应 Agent 执行，结果反馈给 Chief。

```
Chief 输出:  "DELEGATE TO searcher:\nQuery: RLHF survey..."
                │
Router 解析:  ("searcher", "Query: RLHF survey...")
                │
执行:         searcher.reply(task)
                │
结果反馈:     Chief 看到 Searcher 的输出，决定下一步
```

### Agent 生命周期

```
程序启动 → ResearchTeam.__init__()
            ├─ Agent("chief", ...)       对象创建
            ├─ Agent("searcher", ...)     常驻内存
            ├─ Agent("analyst", ...)      等待调用
            ├─ Agent("synthesizer", ...)
            └─ Agent("ideator", ...)
               │
用户请求 → strategy.execute(team, msg)
            └─ while 循环: 委派 → 执行 → 反馈 → 委派 → ...
               │
响应完成 → 返回最终 Msg，Agent 对象继续常驻
```

所有 Agent 在启动时一次性创建，运行时通过消息路由协作。没有动态 spawn，没有进程/线程创建。

---

## 配置

### 内置预设

| 预设 | Agent | 策略 | 适用场景 |
|------|-------|------|---------|
| `quick_survey` | searcher, chief | pipeline | 快速文献概览 |
| `idea_generation` | 全部 5 个 | autonomous | 深度分析 + 创意生成 |

### 自定义 YAML

```yaml
name: my_research
orchestration:
  strategy: autonomous
  max_rounds: 15

agents:
  - name: chief
    role: chief
    model: deepseek-chat
    tools: [TaskCreate, TaskList]

  - name: searcher
    role: searcher
    model: deepseek-chat
    tools: [search_arxiv, get_paper_detail]

  - name: analyst
    role: analyst
    model: deepseek-chat
    tools: [get_paper_detail]

  - name: synthesizer
    role: synthesizer
    model: deepseek-chat
    tools: [search_arxiv]

  - name: ideator
    role: ideator
    model: deepseek-reasoner
    tools: [search_arxiv]
```

### 可用工具

| 工具 | 类型 | 说明 |
|------|------|------|
| `search_arxiv` | FunctionTool | arxiv 关键词检索 |
| `get_paper_detail` | FunctionTool | 获取论文完整摘要 |
| `TaskCreate` | v2.0 内置 | 创建结构化子任务 |
| `TaskList` | v2.0 内置 | 列出当前任务及状态 |

---

## 项目结构

```
idea_creator/
├── __init__.py              # 包入口 + research() API + .env 加载
├── main.py                  # CLI 入口
├── pyproject.toml           # 依赖声明
├── .env.example
├── .gitignore
│
├── agents/                  # Agent 层
│   ├── factory.py           # build_agent() 工厂
│   ├── prompts.py           # 5 个角色的 system prompt 模板
│   └── team.py              # ResearchTeam 容器 + 工具注册
│
├── tools/                   # 工具层
│   ├── arxiv.py             # search_arxiv, get_paper_detail
│   └── utils.py             # HTTP 客户端, XML 解析, 格式化
│
├── orchestration/           # 编排层
│   ├── base.py              # OrchestrationStrategy 抽象基类
│   ├── autonomous.py        # Chief 驱动动态委派
│   ├── pipeline.py          # 固定序列执行
│   └── router.py            # DELEGATE TO 指令解析
│
└── config/                  # 配置层
    ├── models.py            # Pydantic 校验模型
    ├── loader.py            # YAML 加载 + 编程式 API
    └── presets/             # 内置预设
        ├── quick_survey.yaml
        └── idea_generation.yaml
```

---

## 需求

- Python >= 3.11
- AgentScope >= 2.0
- DeepSeek API Key

## License

MIT
