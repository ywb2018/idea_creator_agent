# Idea Creator

A **harness-based** multi-agent system for research paper search, critical analysis, and novel idea generation — built on [AgentScope](https://github.com/agentscope-ai/agentscope).

## What It Does

Idea Creator deploys a team of LLM-powered agents that collaborate to:

1. **Search** for papers on arxiv by keyword or topic
2. **Analyze** individual papers critically (problem, method, strengths, weaknesses)
3. **Synthesize** findings across papers (gaps, trends, conflicts)
4. **Generate** novel research ideas from the synthesis

## Architecture: Harness, Not Workflow

The system is a **harness** — agents are composable building blocks with swappable orchestration strategies:

| Concept | Implementation |
|---------|---------------|
| **Agents** | 5 specialized roles: Chief, Searcher, Analyst, Synthesizer, Ideator |
| **Orchestration** | Swappable strategies: Autonomous (Chief-driven) or Pipeline (fixed sequence) |
| **Configuration** | YAML presets + Pydantic validation — compose teams without code changes |
| **Models** | Per-agent model selection — use reasoning models for Chief/Ideator, fast models for workers |

## Quick Start

### Installation

```bash
pip install agentscope httpx pyyaml pydantic
```

### Set API Key

```powershell
# PowerShell
$env:DEEPSEEK_API_KEY = "sk-..."
```

```bash
# Bash
export DEEPSEEK_API_KEY="sk-..."
```

### Run

```bash
# Quick literature survey
python main.py "recent advances in multi-agent LLM systems" --preset quick_survey

# Full idea generation
python main.py "What are open problems in mechanistic interpretability?" --preset idea_generation

# Custom config
python main.py "Survey RLHF alternatives" --config my_config.yaml
```

### Programmatic API

```python
import asyncio
from idea_creator import research

async def main():
    result = await research(
        "LLM agents for code generation",
        preset="idea_generation",
        api_key="sk-...",
    )
    print(result)

asyncio.run(main())
```

## Agent Roles

| Agent | Role | Tools |
|-------|------|-------|
| **Chief** | Orchestrates the team, delegates tasks, synthesizes final reports | None |
| **Searcher** | Finds papers on arxiv by keyword queries | `search_arxiv`, `get_paper_detail` |
| **Analyst** | Deep critical analysis of individual papers | `get_paper_detail` |
| **Synthesizer** | Cross-paper comparison, gap analysis, trend identification | `search_arxiv` |
| **Ideator** | Generates novel research ideas from synthesis | `search_arxiv` |

## Orchestration Strategies

### Autonomous (default for idea_generation)

The Chief dynamically decides which specialist to call next based on intermediate results. Supports adaptive research — the Chief can re-search with different queries, skip unnecessary steps, or go deeper where needed.

### Pipeline (default for quick_survey)

Fixed sequence of agent invocations. Predictable and fast.

Built-in pipeline presets:
- `quick_survey`: searcher → chief
- `standard_analysis`: searcher → analyst → chief
- `deep_analysis`: searcher → analyst → synthesizer → chief
- `idea_generation`: searcher → analyst → synthesizer → ideator → chief

## Configuration

### Built-in Presets

```bash
python main.py "your question" --preset quick_survey     # Fast overview
python main.py "your question" --preset idea_generation   # Deep + ideas
```

### Custom YAML Config

```yaml
name: my_research
description: "Custom research setup"

orchestration:
  strategy: autonomous    # or "pipeline"
  max_rounds: 15

model_defaults:
  chief: deepseek-reasoner
  searcher: deepseek-chat

agents:
  - name: chief
    role: chief
    model: deepseek-reasoner
    tools: []

  - name: searcher
    role: searcher
    model: deepseek-chat
    tools: [search_arxiv, get_paper_detail]
```

## Project Structure

```
idea_creator/
├── __init__.py              # Package root + research() convenience API
├── main.py                  # CLI entry point
├── pyproject.toml
│
├── agents/                  # Agent definitions
│   ├── factory.py           # build_agent() — generic agent factory
│   ├── prompts.py           # System prompt templates for all 5 roles
│   └── team.py              # ResearchTeam container
│
├── tools/                   # Tools agents can use
│   ├── arxiv.py             # search_arxiv, get_paper_detail
│   └── utils.py             # HTTP client, XML parsing, formatting
│
├── orchestration/           # How agents coordinate
│   ├── base.py              # OrchestrationStrategy abstract base
│   ├── autonomous.py        # Chief-driven dynamic delegation
│   ├── pipeline.py          # Fixed-sequence execution
│   └── router.py            # DELEGATE TO parser
│
└── config/                  # YAML-driven configuration
    ├── models.py            # Pydantic validation schemas
    ├── loader.py            # YAML loading + programmatic API
    └── presets/             # Built-in research modes
        ├── quick_survey.yaml
        └── idea_generation.yaml
```

## Requirements

- Python >= 3.11
- AgentScope
- httpx
- PyYAML
- Pydantic >= 2.0
- DeepSeek API key (or any OpenAI-compatible provider)

## License

MIT
