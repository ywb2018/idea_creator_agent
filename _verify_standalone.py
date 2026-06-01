"""Standalone verification — tests modules without AgentScope deps."""
import sys
import os
import importlib
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(os.path.abspath(__file__))

print("=== Test 1: Syntax check all Python files ===")
import py_compile

py_files = []
for root, dirs, files in os.walk(project_root):
    for f in files:
        if f.endswith('.py') and not f.startswith('_verify'):
            py_files.append(os.path.join(root, f))

for fpath in sorted(py_files):
    try:
        py_compile.compile(fpath, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"  SYNTAX ERROR: {fpath}: {e}")
        sys.exit(1)
print(f"  All {len(py_files)} files: syntax OK")

# Test 2: Router (no external deps beyond stdlib)
# Must load directly to avoid orchestration/__init__.py which chains to AgentScope
print("\n=== Test 2: Delegation parser ===")
import importlib.util
_router_spec = importlib.util.spec_from_file_location(
    "router", os.path.join(project_root, "orchestration", "router.py")
)
router = importlib.util.module_from_spec(_router_spec)
_router_spec.loader.exec_module(router)

name, task = router.parse_delegation("DELEGATE TO searcher:\nQuery: LLM agents\nMax: 5")
assert name == "searcher", f"Expected searcher, got {name}"
assert "LLM agents" in task
print("  Basic delegation: OK")

name2, task2 = router.parse_delegation("Here is the final report.")
assert name2 is None
print("  No delegation: OK")

text_multi = """DELEGATE TO searcher:
Find papers on topic A.

DELEGATE TO analyst:
Analyze the papers."""
all_dels = router.extract_all_delegations(text_multi)
assert len(all_dels) == 2
print(f"  Multi-delegation: OK ({len(all_dels)} found)")

name3, _ = router.parse_delegation("delegate to ANALYST:\nanalyze this")
assert name3 == "analyst"
print("  Case insensitive: OK")

assert router.has_delegation("DELEGATE TO searcher: find")
assert not router.has_delegation("normal response")
print("  has_delegation helper: OK")

# Test 3: Prompts (load directly to avoid agents/__init__.py)
print("\n=== Test 3: Prompt templates ===")
_prompts_spec = importlib.util.spec_from_file_location(
    "prompts", os.path.join(project_root, "agents", "prompts.py")
)
prompts = importlib.util.module_from_spec(_prompts_spec)
_prompts_spec.loader.exec_module(prompts)

roles = prompts.list_roles()
assert len(roles) == 5
assert "chief" in roles
assert "ideator" in roles

for role in roles:
    p = prompts.get_prompt(role)
    assert len(p) > 200, f"Prompt for {role} too short: {len(p)}c"
    # Verify key content sections exist
    if role == "chief":
        assert "DELEGATE TO" in p, "Chief prompt must mention delegation protocol"
    if role == "ideator":
        assert "Gap-filling" in p or "gap" in p.lower(), "Ideator needs strategies"
print(f"  All {len(roles)} prompts OK (sizes: {', '.join(f'{r}:{len(prompts.get_prompt(r))}c' for r in roles)})")

# Test 4: Config loading (YAML only — Pydantic needs Python 3.9+)
print("\n=== Test 4: Config loading ===")
import yaml

presets_dir = os.path.join(project_root, "config", "presets")
presets = sorted(p.stem for p in Path(presets_dir).glob("*.yaml"))
print(f"  Available presets: {presets}")
assert "quick_survey" in presets
assert "idea_generation" in presets

# Verify YAML files are valid
for preset_name in presets:
    path = os.path.join(presets_dir, f"{preset_name}.yaml")
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    assert "name" in data
    assert "agents" in data
    assert "orchestration" in data
    print(f"  {preset_name}.yaml: {len(data['agents'])} agents, strategy={data['orchestration']['strategy']}")

# Try Pydantic validation (requires Python 3.9+)
try:
    from config.loader import load_preset, create_config
    from config.models import AgentSpec, ResearchModeConfig
    from pydantic import ValidationError

    config = load_preset("quick_survey")
    assert config.name == "quick_survey"
    assert len(config.agents) == 2
    print("  Pydantic quick_survey: OK")

    config2 = load_preset("idea_generation")
    assert config2.name == "idea_generation"
    assert len(config2.agents) == 5
    print("  Pydantic idea_generation: OK")

    # Validation
    try:
        AgentSpec(name="test", role="invalid_role")
        assert False
    except ValidationError:
        print("  Pydantic validation: OK")

    cfg = create_config(
        name="test",
        description="test",
        strategy="pipeline",
        agents=[
            {"name": "chief", "role": "chief"},
            {"name": "searcher", "role": "searcher", "tools": ["search_arxiv"]},
        ],
        sequence=["searcher", "chief"],
    )
    assert len(cfg.agents) == 2
    print("  Programmatic config: OK")
except TypeError as e:
    print(f"  (Skipped Pydantic tests — requires Python 3.9+: {e})")

# Test 5: Tools utils (load directly to avoid tools/__init__.py)
print("\n=== Test 5: Tools utils ===")
_utils_spec = importlib.util.spec_from_file_location(
    "utils", os.path.join(project_root, "tools", "utils.py")
)
tu = importlib.util.module_from_spec(_utils_spec)
_utils_spec.loader.exec_module(tu)
# Verify the XML parsing function works
import xml.etree.ElementTree as ET
sample_xml = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2402.14034v1</id>
    <title>Test Paper Title</title>
    <summary>This is a test abstract.</summary>
    <published>2024-02-21</published>
    <author><name>Author One</name></author>
    <author><name>Author Two</name></author>
    <category term="cs.AI"/>
    <link title="pdf" href="http://arxiv.org/pdf/2402.14034v1"/>
  </entry>
</feed>"""
root = ET.fromstring(sample_xml)
entry = root.find("{http://www.w3.org/2005/Atom}entry")
paper = tu.extract_arxiv_paper_info(entry)
assert paper["arxiv_id"] == "2402.14034v1"
assert paper["title"] == "Test Paper Title"
assert len(paper["authors"]) == 2
assert paper["pdf_url"] != ""
print("  XML parsing: OK")
print(f"  Extracted: {paper['arxiv_id']} - {paper['title']}")

# Test formatting
summary = tu.format_paper_summary(paper, index=1)
assert "2402.14034v1" in summary
assert "### 1." in summary
detail = tu.format_paper_detail(paper)
assert "### Abstract" in detail
assert "2402.14034v1" in detail
print("  Formatting: OK")

print("\n" + "=" * 60)
print("=== ALL STANDALONE TESTS PASSED ===")
print("=" * 60)
print("(Full integration tests require Python >= 3.11 and AgentScope)")
print("Run with: python main.py 'research question' --preset quick_survey")
