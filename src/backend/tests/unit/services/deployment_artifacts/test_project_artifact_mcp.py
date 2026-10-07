"""Unit tests for MCP requirement collection in the project-artifact builder.

Targets the private helpers directly, matching ``test_project_artifact_providers.py``.

The distinction every test here circles is the one the deploy has to make: an
external server's credential can only be supplied where the flow runs, while one
of our own projects can be rebuilt at deploy with a key minted on the target. Read
the wrong way round, an external server gets handed a key for our serving plane.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.deployment_artifacts.builder import (
    ProjectArtifactLimits,
    ProjectArtifactRequiredMcpProject,
    _build_deployment_snapshot_flows,
    _collect_mcp_requirements,
    _FlowSnapshot,
    _McpRequirements,
)
from langflow.utils.mcp_config_secrets import project_id_from_mcp_url, variable_name_for, variable_reference_name

SIBLING = "9a2c1f44-0b7e-4d3a-8c21-77f0e5b4d900"


def _flow(*servers: dict, nested: dict | None = None) -> dict:
    """A flow whose nodes hold one MCP field per server, optionally one nested."""
    node: dict = {
        "data": {"node": {"template": {f"mcp_{i}": {"type": "mcp", "value": s} for i, s in enumerate(servers)}}}
    }
    if nested is not None:
        node["data"]["node"]["flow"] = {
            "data": {"nodes": [{"data": {"node": {"template": {"mcp_n": {"type": "mcp", "value": nested}}}}}]}
        }
    return {"nodes": [node], "edges": []}


def _server(name: str, config: dict) -> dict:
    return {"name": name, "config": config}


# --- what counts as a variable -------------------------------------------------


def test_placeholder_header_is_reported_by_name_without_its_braces():
    flow = _flow(_server("stripe", {"url": "https://api.stripe.com/mcp", "headers": {"Auth": "{{MCP_STRIPE}}"}}))
    assert _collect_mcp_requirements(flow).variables == ("MCP_STRIPE",)


def test_a_generated_variable_name_is_reported_as_itself():
    name = variable_name_for("billing-mcp", "Authorization")
    flow = _flow(_server("billing", {"url": "https://b.example/mcp", "env": {"TOKEN": name}}))
    assert _collect_mcp_requirements(flow).variables == (name,)


def test_a_non_secret_header_is_not_a_requirement():
    """``Accept`` is on the allowlist the scrubber skips, so it names no variable."""
    flow = _flow(_server("stripe", {"url": "https://api.stripe.com/mcp", "headers": {"Accept": "application/json"}}))
    assert _collect_mcp_requirements(flow) == _McpRequirements()


@pytest.mark.parametrize(
    "value",
    [
        "Bearer sk_live_51H8xQ2",
        # AWS's own documentation key, shaped exactly like the thing that must not
        # pass: an uppercase token a looser rule would read as a variable name.
        "AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
        "",
        "   ",
    ],
)
def test_a_literal_value_is_never_mistaken_for_a_variable(value):
    """Reading any capitalised token as a reference would fail open on the secret itself."""
    assert variable_reference_name(value) is None


# --- what counts as one of our projects ----------------------------------------


def test_a_sibling_project_url_is_reported_with_the_name_the_flow_calls_it_by():
    """The name travels because the flow resolves by it.

    A rebuilt connection stored under any other name is a row the flow never finds.
    """
    flow = _flow(_server("billing", {"url": f"http://localhost:7860/api/v1/mcp/project/{SIBLING}/streamable"}))
    requirements = _collect_mcp_requirements(flow)
    assert requirements.projects == (ProjectArtifactRequiredMcpProject(server_name="billing", project_id=SIBLING),)
    assert requirements.variables == ()


def test_a_server_with_no_name_declares_no_project():
    """Without a name there is nothing to key a rebuilt connection on."""
    flow = _flow({"config": {"url": f"http://localhost:7860/api/v1/mcp/project/{SIBLING}/streamable"}})
    assert _collect_mcp_requirements(flow).projects == ()


def test_an_external_url_names_no_project():
    assert _collect_mcp_requirements(_flow(_server("stripe", {"url": "https://api.stripe.com/v1/mcp"}))).projects == ()


def test_a_url_held_in_a_variable_is_asked_for_rather_than_resolved():
    """It names no project until it resolves, so it is reported as a variable and treated as external.

    Being wrong this way asks for something harmless. The other way mints a key for a stranger.
    """
    requirements = _collect_mcp_requirements(_flow(_server("mystery", {"url": "{{MCP_SERVER_URL}}"})))
    assert requirements.variables == ("MCP_SERVER_URL",)
    assert requirements.projects == ()


@pytest.mark.parametrize(
    "url",
    [
        f"https://elsewhere.example/?next=/api/v1/mcp/project/{SIBLING}/streamable",
        f"https://elsewhere.example/redirect/api/v1/mcp/project/{SIBLING}/streamable",
        "https://elsewhere.example/api/v1/mcp/project/not-a-uuid/streamable",
    ],
)
def test_a_path_that_only_resembles_ours_names_no_project(url):
    """The shape has to be the whole path.

    Carried in a query string it would have been read as one of our own projects
    and rebuilt with a key minted for this plane.
    """
    assert project_id_from_mcp_url(url) is None
    assert _collect_mcp_requirements(_flow(_server("spoof", {"url": url}))).projects == ()


def test_our_shape_on_another_host_still_names_the_project():
    """Deliberate: this answers which project a path names, never whether it is ours.

    The caller confirms a sibling by looking the id up locally, not by checking the
    host, because a rebuilt connection carries the target's own address and discards
    whatever origin was configured.
    """
    assert project_id_from_mcp_url(f"https://elsewhere.example/api/v1/mcp/project/{SIBLING}/streamable") == SIBLING


# --- traversal and merging ------------------------------------------------------


def test_a_server_inside_a_grouped_node_is_found():
    flow = _flow(
        _server("stripe", {"url": "https://api.stripe.com/mcp", "headers": {"Auth": "{{MCP_STRIPE}}"}}),
        nested=_server("billing", {"url": f"http://localhost:7860/api/v1/mcp/project/{SIBLING}/sse"}),
    )
    requirements = _collect_mcp_requirements(flow)
    assert requirements.variables == ("MCP_STRIPE",)
    assert [project.project_id for project in requirements.projects] == [SIBLING]


@pytest.mark.parametrize("flow_data", [None, "nope", {}, {"nodes": "nope"}, {"nodes": [None, 1, "x"]}])
def test_unreadable_flow_data_collects_nothing_rather_than_raising(flow_data):
    assert _collect_mcp_requirements(flow_data) == _McpRequirements()


def test_merging_deduplicates_across_flows():
    external = _server("stripe", {"url": "https://api.stripe.com/mcp", "headers": {"Auth": "{{MCP_STRIPE}}"}})
    sibling = _server("billing", {"url": f"http://localhost:7860/api/v1/mcp/project/{SIBLING}/streamable"})
    merged = _McpRequirements.merged(
        [_collect_mcp_requirements(_flow(external)), _collect_mcp_requirements(_flow(sibling, external))]
    )
    assert merged.variables == ("MCP_STRIPE",)
    assert [project.project_id for project in merged.projects] == [SIBLING]


# --- the snapshot carries them --------------------------------------------------


def test_a_deployment_snapshot_reports_what_its_flows_need():
    snapshot = _FlowSnapshot(
        flow_id=uuid4(),
        name="support",
        payload={
            "data": _flow(
                _server("stripe", {"url": "https://api.stripe.com/mcp", "headers": {"Auth": "{{MCP_STRIPE}}"}}),
                _server("billing", {"url": f"http://localhost:7860/api/v1/mcp/project/{SIBLING}/streamable"}),
            )
        },
    )
    *_, requirements = _build_deployment_snapshot_flows((snapshot,), limits=ProjectArtifactLimits())
    assert requirements.variables == ("MCP_STRIPE",)
    assert [(p.server_name, p.project_id) for p in requirements.projects] == [("billing", SIBLING)]


def test_a_project_with_no_mcp_servers_reports_nothing():
    snapshot = _FlowSnapshot(flow_id=uuid4(), name="plain", payload={"data": {"nodes": [], "edges": []}})
    *_, requirements = _build_deployment_snapshot_flows((snapshot,), limits=ProjectArtifactLimits())
    assert requirements == _McpRequirements()


# --- the packaged artifact says the same thing as the snapshot ------------------


def _archive(*snapshots: _FlowSnapshot):
    from langflow.services.deployment_artifacts.builder import _build_archive

    return _build_archive(
        project_id=uuid4(),
        project_name="support",
        snapshots=snapshots,
        limits=ProjectArtifactLimits(),
    )


def _manifest(artifact) -> dict:
    import io
    import json
    import zipfile

    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        return json.loads(archive.read("manifest.json"))


def _mcp_snapshot() -> _FlowSnapshot:
    return _FlowSnapshot(
        flow_id=uuid4(),
        name="support",
        payload={
            "data": _flow(
                _server("stripe", {"url": "https://api.stripe.com/mcp", "headers": {"Auth": "{{MCP_STRIPE}}"}}),
                _server("billing", {"url": f"http://localhost:7860/api/v1/mcp/project/{SIBLING}/streamable"}),
            )
        },
    )


def test_a_packaged_artifact_reports_the_same_requirements_as_a_snapshot():
    """Both deploy paths have to declare the same thing.

    A precheck whose answer depended on which path the caller took would pass a
    project one way and refuse it the other.
    """
    snapshot = _mcp_snapshot()
    manifest = _manifest(_archive(snapshot))
    *_, from_snapshot = _build_deployment_snapshot_flows((snapshot,), limits=ProjectArtifactLimits())

    assert manifest["required_mcp_variables"] == list(from_snapshot.variables)
    assert manifest["required_mcp_projects"] == [
        {"server_name": p.server_name, "project_id": p.project_id} for p in from_snapshot.projects
    ]


def test_the_manifest_claims_v6_only_when_there_is_something_to_declare():
    with_mcp = _manifest(_archive(_mcp_snapshot()))
    without = _manifest(_archive(_FlowSnapshot(flow_id=uuid4(), name="plain", payload={"data": {"nodes": []}})))

    assert with_mcp["schema_version"] == 6
    assert without["schema_version"] < 6


def test_a_project_with_no_mcp_servers_packages_exactly_as_before():
    """The keys are omitted rather than emitted empty, so an older reader sees no change."""
    manifest = _manifest(_archive(_FlowSnapshot(flow_id=uuid4(), name="plain", payload={"data": {"nodes": []}})))

    assert "required_mcp_variables" not in manifest
    assert "required_mcp_projects" not in manifest
    assert all("required_mcp_variables" not in flow for flow in manifest["flows"])
