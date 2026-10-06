"""Updated Agent assets must remain trusted by saved-flow source validation."""

import json
from pathlib import Path

from lfx.utils.flow_validation import (
    _compute_code_hash,
    code_hash_matches_any_template,
    collect_code_by_hash,
    collect_component_hash_lookups,
)

ROOT = Path(__file__).resolve().parents[6]
SOURCE = ROOT / "src/lfx/src/lfx/components/models_and_agents/agent.py"
INDEX = ROOT / "src/lfx/src/lfx/_assets/component_index.json"


def _agent_nodes(value):
    if isinstance(value, dict):
        template = value.get("template")
        field = template.get("code") if isinstance(template, dict) else None
        code = field.get("value") if isinstance(field, dict) else None
        if isinstance(code, str) and "class AgentComponent(" in code:
            yield value
        for child in value.values():
            yield from _agent_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _agent_nodes(child)


def test_published_agent_source_is_trusted_for_flow_validation():
    catalog = dict(json.loads(INDEX.read_text())["entries"])
    source = SOURCE.read_text()
    _types, hashes = collect_component_hash_lookups(catalog)
    trusted = collect_code_by_hash(catalog)

    assert code_hash_matches_any_template(source, hashes)
    assert trusted[_compute_code_hash(source)] == source


def test_agent_starters_use_current_trusted_source_and_metadata():
    source = SOURCE.read_text()
    source_hash = _compute_code_hash(source)
    files = list((ROOT / "src/backend/base/langflow/initial_setup/starter_projects").glob("*.json"))
    files.extend((ROOT / "src/bundles").glob("**/starter_projects/*.json"))
    found = 0

    for path in files:
        for node in _agent_nodes(json.loads(path.read_text())):
            assert node["template"]["code"]["value"] == source, path
            assert node["metadata"]["code_hash"] == source_hash, path
            found += 1
    assert found > 0
