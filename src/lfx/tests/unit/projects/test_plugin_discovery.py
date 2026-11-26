"""Discover actual distribution metadata and import plugin code, without mocking entry points."""

from __future__ import annotations

import importlib
import importlib.metadata
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from lfx.projects import (
    ProjectTypeDefinition,
    all_project_types,
    apply_project_config,
    get_project_type,
    register_project_type,
    registered_project_types,
)


@pytest.fixture
def installed_plugin(monkeypatch, tmp_path):
    """Lay out an installed distribution, including its real entry_points.txt metadata.

    The same fixture can be built and installed with uv/pip using its pyproject.toml. Keeping
    the test install local avoids a package manager, network, or build backend in pytest.
    """
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    fixture = Path(__file__).parents[2] / "data" / "project_type_plugin"
    project = tomllib.loads((fixture / "pyproject.toml").read_text())["project"]
    site = tmp_path / "site-packages"
    shutil.copytree(fixture / "sample_project_types", site / "sample_project_types")
    info = site / "lfx_test_project_types-0.0.1.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {project['name']}\nVersion: {project['version']}\n")
    entrypoints = info / "entry_points.txt"
    entrypoints.write_text(
        "[lfx.project_type.adapters]\n"
        + "".join(f"{key} = {value}\n" for key, value in project["entry-points"]["lfx.project_type.adapters"].items())
    )
    monkeypatch.syspath_prepend(str(site))
    yield entrypoints
    sys.modules.pop("sample_project_types", None)


@pytest.mark.usefixtures("installed_plugin")
def test_installed_package_exposes_form_and_writes_through(isolated_project_registry):
    assert not isolated_project_registry.is_discovered
    assert "sample_project_types" not in sys.modules
    distribution = importlib.metadata.distribution("lfx-test-project-types")
    assert distribution.version == "0.0.1"

    project_type = get_project_type("support-desk")

    assert type(project_type).__module__ == "sample_project_types"
    assert project_type.sections() == ("Instructions",)
    field = project_type.to_template()["instructions"]
    assert field["value"] == "Help the customer."
    assert field["flow_contract"]["name"] == "Instructions"
    assert field["supports_flow_binding"] is True
    assert [t.name for t in all_project_types()] == list(registered_project_types())
    flow = {
        "nodes": [
            {
                "id": "Agent-1",
                "data": {
                    "type": "Agent",
                    "node": {
                        "template": {"system_prompt": {"value": "Original"}},
                    },
                },
            }
        ],
        "edges": [],
    }
    changed = apply_project_config(flow, project_type, {"instructions": "Answer briefly."})
    assert changed.inputs_written == 1
    assert changed.data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] == "Answer briefly."
    assert flow["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] == "Original"


@pytest.mark.parametrize(
    ("filename", "section"),
    [("lfx.toml", "project_type.adapters"), ("pyproject.toml", "tool.lfx.project_type.adapters")],
)
@pytest.mark.usefixtures("installed_plugin")
def test_operator_config_overrides_host_and_entry_point(tmp_path, filename, section):
    plugin = importlib.import_module("sample_project_types")

    class HostSupportDeskType(plugin.SupportDeskType):
        display_name = "Host support desk"

    register_project_type(HostSupportDeskType)
    (tmp_path / filename).write_text(f'[{section}]\nsupport-desk = "sample_project_types:OperatorSupportDeskType"\n')

    assert isinstance(get_project_type("support-desk"), plugin.OperatorSupportDeskType)


@pytest.mark.usefixtures("installed_plugin")
def test_entry_point_cannot_replace_an_explicit_registration():
    plugin = importlib.import_module("sample_project_types")

    class HostSupportDeskType(plugin.SupportDeskType):
        display_name = "Host support desk"

    register_project_type(HostSupportDeskType)
    assert isinstance(get_project_type("support-desk"), HostSupportDeskType)


@pytest.mark.usefixtures("installed_plugin")
def test_host_override_requires_explicit_intent():
    plugin = importlib.import_module("sample_project_types")
    register_project_type(plugin.SupportDeskType)
    with pytest.raises(ValueError, match="already registered"):
        register_project_type(plugin.OperatorSupportDeskType)
    register_project_type(plugin.OperatorSupportDeskType, override=True)
    assert isinstance(get_project_type("support-desk"), plugin.OperatorSupportDeskType)


@pytest.mark.usefixtures("installed_plugin")
def test_late_registration_cannot_override_resolved_operator_config(tmp_path):
    plugin = importlib.import_module("sample_project_types")
    (tmp_path / "lfx.toml").write_text(
        '[project_type.adapters]\nsupport-desk = "sample_project_types:OperatorSupportDeskType"\n'
    )
    configured = get_project_type("support-desk")
    with pytest.raises(ValueError, match="before the first lookup"):
        register_project_type(plugin.SupportDeskType, override=True)
    assert get_project_type("support-desk") is configured


@pytest.mark.usefixtures("installed_plugin")
def test_configuration_prefers_lfx_toml(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.lfx.project_type.adapters]\nsupport-desk = "sample_project_types:OperatorSupportDeskType"\n'
    )
    (tmp_path / "lfx.toml").write_text("[project_type.adapters]\n")
    assert get_project_type("support-desk").display_name == "Support desk"


@pytest.mark.parametrize(
    "target", ["builtins:dict", "sample_project_types:SupportDeskType", "missing_plugin:MissingType"]
)
def test_bad_entry_point_does_not_hide_working_types(installed_plugin, target):
    with installed_plugin.open("a") as stream:
        stream.write(f"bad-plugin = {target}\n")
    assert get_project_type("support-desk").name == "support-desk"
    assert get_project_type("agent-harness").name == "agent-harness"
    with pytest.raises(ValueError, match="not registered"):
        get_project_type("bad-plugin")


def test_type_unavailable_after_restart_has_no_fallback():
    with pytest.raises(ValueError, match=r"support-desk.*not registered"):
        get_project_type("support-desk")


@pytest.mark.usefixtures("installed_plugin")
def test_concurrent_first_lookups_share_the_discovered_declaration():
    with ThreadPoolExecutor(max_workers=4) as pool:
        declarations = list(pool.map(get_project_type, ["support-desk"] * 8))
    assert all(declaration is declarations[0] for declaration in declarations)


def test_lookup_during_plugin_import_fails_without_deadlocking(installed_plugin):
    module = installed_plugin.parent.parent / "sample_project_types" / "__init__.py"
    with module.open("a") as stream:
        stream.write('\nfrom lfx.projects import get_project_type\nget_project_type("flows")\n')
    # Adapter discovery isolates the failing entry point and still serves built-ins.
    assert get_project_type("flows").name == "flows"
    with pytest.raises(ValueError, match=r"support-desk.*not registered"):
        get_project_type("support-desk")


@pytest.mark.parametrize(
    "attributes",
    [{}, {"name": "missing-label"}, {"name": "bad-fields", "display_name": "Bad", "icon": "Box", "fields": []}],
)
def test_direct_registration_rejects_invalid_declarations(attributes):
    definition = type("InvalidType", (ProjectTypeDefinition,), attributes)
    with pytest.raises((TypeError, ValueError)):
        register_project_type(definition)


@pytest.mark.parametrize("agent_first", [False, True])
def test_fresh_imports_do_not_discover_plugins_or_depend_on_import_order(agent_first):
    code = """
import importlib.metadata
original = importlib.metadata.entry_points
project_discovery_calls = []
def guard(*args, **kwargs):
    if kwargs.get("group") == "lfx.project_type.adapters":
        project_discovery_calls.append(kwargs)
        raise AssertionError("Project discovery ran during import")
    return original(*args, **kwargs)
importlib.metadata.entry_points = guard
"""
    modules = ["lfx.projects", "lfx.components.models_and_agents.agent"]
    if agent_first:
        modules.reverse()
    code += "\n".join(f"import {module}" for module in modules)
    code += "\nassert not project_discovery_calls, project_discovery_calls\n"
    completed = subprocess.run(  # noqa: S603 -- interpreter and import script are controlled by this test
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30, check=False
    )
    assert completed.returncode == 0, completed.stderr
