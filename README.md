# Idea Creator

基于 [AgentScope](https://github.com/agentscope-ai/agentscope) v2.0 构建的**多 Agent 论文检索、分析与创意生成系统**。

## 快速开始

### 安装

```bash
pip install agentscope httpx pyyaml pydantic python-dotenv
```

### 配置

```bash
# 编辑 .env 填入 DEEPSEEK_API_KEY=sk-...
```

### 运行

```bash
# 使用所有 Agent，自主模式
python main.py "recent advances in multi-agent LLM systems"

# 指定部分 Agent
python main.py "open problems in ML" --agents chief,searcher,ideator

# 使用 pipeline 策略
python main.py "survey RLHF" --strategy pipeline

# 用 YAML 编排配置
python main.py "review RLHF" --config orchestration.yaml
```

```python
# 编程调用
from idea_creator import research

# 所有 Agent
result = await research("LLM agents for code generation")

# 指定 Agent + 策略
result = await research(
    "survey RLHF",
    agent_names=["chief", "searcher", "analyst"],
    strategy="pipeline",
)
```

---

## 设计架构

### 整体架构：三层解耦

```
┌─────────────────────────────────────────────────────────┐
│  Agent 定义层  — agents/definitions/*.md                │
│                                                         │
│  每个 .md 文件 = 一个 Agent 的完整定义                     │
│    frontmatter (YAML): name, model, tools, max_iters    │
│    body (markdown):   system_prompt                     │
│                                                         │
│  改 prompt 只需编辑 .md 文件，零代码变更                   │
├─────────────────────────────────────────────────────────┤
│  Agent 运行时层  — ResearchTeam + team.py                │
│                                                         │
│  加载 .md 定义 → 翻译字符串为对象 → 创建 Agent 实例        │
│  每个 Agent = v2.0 Agent 实例，独立 model + toolkit       │
├─────────────────────────────────────────────────────────┤
│  Orchestration Layer — 行为层（Strategy Pattern）        │
│                                                         │
│  可替换的策略接口，定义 Agent 之间如何交互                 │
│    - AutonomousStrategy: Chief 文本委派 + 路由循环       │
│    - PipelineStrategy: 固定序列执行                      │
└─────────────────────────────────────────────────────────┘
```

### Agent 角色

| Agent | .md 文件 | 工具 | 职责 |
|-------|---------|------|------|
| **chief** | chief.md | TaskCreate, TaskList | 理解意图、委派任务、合成报告 |
| **searcher** | searcher.md | search_arxiv, filter_papers_by_year, remove_paper | arxiv 论文检索 + 时间过滤 + 语义筛选 |
| **analyst** | analyst.md | get_paper_detail | 单篇论文深度批判分析 |
| **synthesizer** | synthesizer.md | search_arxiv | 多篇论文横向综合、找空白 |
| **ideator** | ideator.md | search_arxiv | 生成新颖研究创意 |

### Agent 定义格式

每个 `agents/definitions/*.md` 文件：

```markdown
---
name: chief
model: deepseek-v4-flash
tools: [TaskCreate, TaskList]
max_iters: 15
---

你是一个**首席研究科学家**...

你的工作流程：
1. 理解用户的研究问题...
2. 委派给专家，使用格式: DELEGATE TO <name>: ...
```

frontmatter 字段：

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | Agent 标识名，用于委派和 team.get_agent() |
| `model` | ❌ | 模型名，默认 deepseek-v4-flash |
| `tools` | ❌ | 工具列表：search_arxiv, filter_papers_by_year, remove_paper, get_paper_detail, TaskCreate, TaskList |
| `max_iters` | ❌ | ReAct 循环最大轮数，默认 15 |

body（frontmatter 之后的 markdown 正文）→ system_prompt。

### 协作流程

```
User: "这个方向有什么 open problems?"

Chief: "拆成几步: 搜索→分析→创意生成"
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
  ├─ DELEGATE TO ideator: 基于 gap 生成创意
  │     └─ Ideator 返回结构化创意
  │
  └─ Chief 合成最终报告 → 返回给 User
```

### 两种编排策略

**Autonomous（默认）**：Chief 动态决策，根据中间结果自适应调整。可重复搜索、跳过步骤、深入感兴趣的方向。`max_rounds` 防止无限循环。

**Pipeline**：固定序列执行，可预测、速度快。适合明确的线性场景。

### 委派机制

Chief 输出文本指令 `DELEGATE TO <agent_name>:` 来委派任务。`router.py` 用正则解析，找到对应 Agent 执行，结果反馈给 Chief。

```
Chief 输出:  "DELEGATE TO searcher:\n查询关键词: RLHF survey..."
Router 解析:  ("searcher", "查询关键词: RLHF survey...")
执行:         team.get_agent("searcher").reply(task)
结果反馈:     Chief 看到输出，决定下一步
```

---

## 使用指南

### CLI

```bash
python main.py "query"                           # 所有 agent，autonomous
python main.py "query" --agents chief,searcher   # 指定 agent
python main.py "query" --strategy pipeline        # pipeline 策略
python main.py "query" --config orchestration.yaml # 编排 YAML
python main.py "query" --max-rounds 10 --quiet    # 控制参数
```

### 编程 API

```python
from idea_creator import research, OrchestrationConfig

# 最简
result = await research("query")

# 指定 agent
result = await research("query", agent_names=["chief", "searcher", "ideator"])

# pipeline
result = await research("query", strategy="pipeline")

# YAML 编排配置
result = await research("query", config="orchestration.yaml")

# OrchestrationConfig 对象
cfg = OrchestrationConfig(strategy="pipeline", sequence=["searcher", "chief"])
result = await research("query", config=cfg)
```

### 编排 YAML

```yaml
strategy: pipeline
max_rounds: 5
sequence: [searcher, analyst, chief]
verbose: true
```

### 添加新 Agent

在 `agents/definitions/` 下新建一个 `.md` 文件即可：

```markdown
---
name: translator
model: deepseek-v4-flash
tools: []
max_iters: 5
---

你是一个翻译专家。将用户提供的内容翻译成中文。
```

无需改任何代码，`ResearchTeam` 会自动发现新文件。

### 可用工具

| 工具 | 类型 | 说明 |
|------|------|------|
| `search_arxiv` | FunctionTool | arxiv 关键词检索，支持 year_from 参数从源头过滤年份 |
| `get_paper_detail` | FunctionTool | 获取单篇论文完整摘要 |
| `filter_papers_by_year` | FunctionTool | 按年份范围过滤已保存论文（兜底） |
| `remove_paper` | FunctionTool | 删除单篇论文（由 LLM 语义判断后调用） |
| `TaskCreate` | v2.0 内置 | 创建结构化子任务 |
| `TaskList` | v2.0 内置 | 列出当前任务及状态 |

---

## 项目结构

```
idea_creator/
├── __init__.py                 # 包入口 + research() API + .env 加载
├── main.py                     # CLI 入口
├── pyproject.toml              # 依赖声明
├── .env                          # API Key 配置
│
├── agents/                     # Agent 定义 + 运行时
│   ├── definitions/            #   .md 文件定义每个 Agent
│   │   ├── chief.md            #     编排者
│   │   ├── searcher.md         #     检索专家
│   │   ├── analyst.md          #     分析专家
│   │   ├── synthesizer.md      #     综合专家
│   │   └── ideator.md          #     创意专家
│   └── team.py                 #   ResearchTeam + .md 加载器 + 工具注册
│
├── tools/                      # 工具实现层
│   ├── arxiv.py                #   search_arxiv, get_paper_detail, filter_*, remove_paper
│   └── utils.py                #   HTTP 客户端, XML 解析, 格式化
│
├── orchestration/              # 编排层
│   ├── base.py                 #   OrchestrationStrategy 抽象基类
│   ├── autonomous.py           #   Chief 驱动动态委派
│   ├── pipeline.py             #   固定序列执行
│   └── router.py               #   DELEGATE TO 指令解析
│
├── papers/                      # 搜索到的论文 JSON（自动生成）
├── reports/                     # 最终研究报告 Markdown（自动生成）
│
└── config/                     # 编排配置
    ├── models.py               #   OrchestrationConfig (Pydantic)
    └── loader.py               #   YAML 加载
```

### 论文过滤流水线

searcher 采用三层过滤确保只保留相关的最新论文：

```
search_arxiv(year_from=2025)    ← ① 源头：年份过滤，旧论文不落盘
  └─ filter_papers_by_year()    ← ② 兜底：年份二次检查
       └─ remove_paper(id)       ← ③ LLM 语义判断：不相关就删
```

## 需求

- Python >= 3.10
- AgentScope >= 2.0
- DeepSeek API Key

## License

MIT
