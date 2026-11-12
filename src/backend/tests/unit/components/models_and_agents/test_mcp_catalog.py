"""Verify that the Editor catalog ships the installed MCP runtime code."""

import json
from importlib.resources import files


def test_mcp_catalog_contains_installed_component_source():
    package = files("lfx")
    index = json.loads(package.joinpath("_assets/component_index.json").read_text(encoding="utf-8"))
    components = dict(index["entries"])["models_and_agents"]
    catalog_source = components["MCPTools"]["template"]["code"]["value"]
    installed_source = package.joinpath("components/models_and_agents/mcp_component.py").read_text(encoding="utf-8")

    assert catalog_source == installed_source, "Regenerate the component index after changing MCP Tools."
