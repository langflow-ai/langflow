"""Regression guards for streaming wiring inside bundled starter projects.

Every starter project that ships an ``Agent`` node MUST embed the post-PR-13358
``AgentComponent`` code — the one whose ``_get_llm`` hard-codes ``stream=True``.
Without this, users importing a starter template inherit the legacy streaming
bug (``openrag_agent.json``-class regression) on the very first flow they
encounter inside Langflow, before the backward-compat shim in
``ToolCallingAgentComponent`` even has a chance to kick in (it covers the
ToolCallingAgent-Classic path; starter projects targeting the modern LangGraph
``AgentComponent`` build a different runnable, so the shim does NOT apply).

These tests are intentionally file-system level: they read the shipped JSON
templates directly, the same way the seeder does at first boot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

STARTER_PROJECTS_DIR = Path(__file__).resolve().parents[3] / "base" / "langflow" / "initial_setup" / "starter_projects"


def _starter_project_files() -> list[Path]:
    if not STARTER_PROJECTS_DIR.is_dir():
        msg = f"starter_projects directory not found at {STARTER_PROJECTS_DIR}"
        raise FileNotFoundError(msg)
    return sorted(STARTER_PROJECTS_DIR.glob("*.json"))


def _agent_nodes_in(path: Path) -> list[dict]:
    flow = json.loads(path.read_text(encoding="utf-8"))
    return [n for n in flow.get("data", {}).get("nodes", []) if n.get("data", {}).get("type") == "Agent"]


def test_should_find_at_least_one_agent_starter_project_so_other_tests_are_meaningful():
    """Smoke test: if no Agent node is found, the rest of this file is vacuous.

    Catches an accidental refactor that renames the ``Agent`` node type
    string (e.g. to ``AgentV2``) — which would otherwise let these scans
    silently skip every flow.
    """
    files = _starter_project_files()
    total_agents = sum(len(_agent_nodes_in(fp)) for fp in files)
    assert total_agents > 0, (
        f"Expected at least one Agent node across {len(files)} starter projects. "
        "If the node type string changed, update _agent_nodes_in()."
    )


@pytest.mark.parametrize("starter_path", _starter_project_files(), ids=lambda p: p.name)
def test_should_embed_stream_true_in_get_llm_when_starter_project_contains_agent(starter_path: Path):
    r"""Every bundled Agent must ship ``_get_llm`` that hard-codes ``stream=True``.

    The starter project JSONs embed a frozen snapshot of the ``AgentComponent``
    class body in ``template['code']['value']``. Langflow ``exec``\s that snapshot
    when the flow loads, so a stale snapshot bypasses any fix made in the live
    ``agent.py`` source — exactly the regression that broke ``openrag_agent.json``
    (code_hash ``154c71cf7441``) and prompted the backward-compat shim in
    ``ToolCallingAgentComponent``.
    """
    agent_nodes = _agent_nodes_in(starter_path)
    if not agent_nodes:
        pytest.skip(f"{starter_path.name} has no Agent node")

    for idx, node in enumerate(agent_nodes):
        template = node.get("data", {}).get("node", {}).get("template", {})
        code_entry = template.get("code", {})
        code_value = code_entry.get("value", "") if isinstance(code_entry, dict) else ""

        assert "def _get_llm" in code_value, (
            f"{starter_path.name}[Agent#{idx}] does not embed _get_llm — the bundled AgentComponent code is malformed."
        )
        assert "stream=True" in code_value, (
            f"{starter_path.name}[Agent#{idx}] embeds an AgentComponent whose "
            "_get_llm() does NOT hard-code stream=True. The starter project is stale; "
            "regenerate it from the live AgentComponent class. Without this, "
            "loading the starter template silently disables Playground streaming."
        )


@pytest.mark.parametrize("starter_path", _starter_project_files(), ids=lambda p: p.name)
def test_should_share_same_agent_code_hash_across_starter_projects(starter_path: Path):
    """All bundled Agents must share a single code_hash.

    Drift between starter projects (e.g. one bundles the new agent.py, another
    still bundles the pre-#13358 version) creates a confusing UX where some
    templates stream and others don't. A single hash is the cheapest invariant
    to assert.
    """
    agent_nodes = _agent_nodes_in(starter_path)
    if not agent_nodes:
        pytest.skip(f"{starter_path.name} has no Agent node")

    # Collect hashes from every starter project at module level.
    all_hashes: set[str] = set()
    for fp in _starter_project_files():
        for node in _agent_nodes_in(fp):
            ch = node.get("data", {}).get("node", {}).get("metadata", {}).get("code_hash")
            if ch:
                all_hashes.add(ch)

    assert len(all_hashes) == 1, (
        f"Starter projects bundle {len(all_hashes)} distinct Agent code_hashes: "
        f"{sorted(all_hashes)!r}. Regenerate the stale templates so streaming behavior "
        "is consistent across all bundled flows."
    )
