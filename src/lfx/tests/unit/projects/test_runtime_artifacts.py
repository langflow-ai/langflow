"""Executable candidates retain dependencies without sharing mutable run state."""

from copy import deepcopy
from uuid import uuid4

import pytest
from lfx.graph import Graph
from lfx.projects.runtime_artifacts import build_candidate, read_candidate


def definition(name, target=None):
    data = {"nodes": [], "edges": []}
    if target:
        data["nodes"] = [
            {
                "id": "RunFlow-1",
                "data": {
                    "type": "RunFlow",
                    "node": {
                        "template": {
                            "flow_id_selected": {"value": target},
                        }
                    },
                },
            }
        ]
    return {"id": str(uuid4()), "name": name, "data": data}


def test_round_trip_and_isolated_definition_reads():
    child = definition("internal")
    root = definition("root", child["id"])
    candidate = build_candidate(root["id"], [root, child])
    restored = read_candidate(candidate.archive())
    assert restored.digest == candidate.digest
    assert restored.manifest["entrypoints"] == [root["id"]]
    restored.definitions[child["id"]]["data"]["nodes"].append({"edited": True})
    assert restored.definitions[child["id"]]["data"]["nodes"] == []
    assert build_candidate(root["id"], [child, root]).archive() == candidate.archive()


def test_graph_copy_and_reset_retain_candidate_but_not_review_cache():
    root = definition("root")
    candidate = build_candidate(root["id"], [root])
    graph = Graph.from_payload(root["data"], instantiate_components=False)
    candidate.bind(graph)
    graph.set_run_id("first")
    graph.reviewed_tool_packs["old"] = {}
    copied = deepcopy(graph)
    assert copied.runtime_candidate.digest == candidate.digest
    assert copied.frozen_tool_flows[root["id"]] == root
    assert copied.reviewed_tool_packs == {}
    graph.set_run_id("second")
    assert graph.frozen_tool_flows[root["id"]] == root
    assert graph.reviewed_tool_packs == {}


def test_missing_and_cyclic_dependencies_are_rejected():
    root = definition("root", str(uuid4()))
    with pytest.raises(ValueError, match="missing"):
        build_candidate(root["id"], [root])
    root["data"]["nodes"][0]["data"]["node"]["template"]["flow_id_selected"]["value"] = root["id"]
    with pytest.raises(ValueError, match="recursive"):
        build_candidate(root["id"], [root])


def rewrite_archive(candidate, *, manifest_change=None, file_change=None, extra=None):
    import io
    import json
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(candidate.archive())) as source, zipfile.ZipFile(buffer, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            if name == "manifest.json" and manifest_change:
                manifest = json.loads(data)
                manifest_change(manifest)
                data = json.dumps(manifest).encode()
            if name.startswith("flows/") and file_change:
                data = file_change(data)
            target.writestr(name, data)
        if extra:
            target.writestr(*extra)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "attack", ["content", "missing", "path", "duplicate", "extra", "version", "size", "digest", "requirements"]
)
def test_invalid_archives_fail_before_component_loading(attack):
    root = definition("root")
    candidate = build_candidate(root["id"], [root], required_variables=("DESTINATION_KEY",))
    if attack == "content":
        raw = rewrite_archive(candidate, file_change=lambda raw: raw + b" ")
    elif attack == "missing":
        raw = rewrite_archive(
            candidate, manifest_change=lambda m: m["flows"][0].update(id=str(uuid4()), path="flows/missing.json")
        )
    elif attack == "path":
        raw = rewrite_archive(candidate, manifest_change=lambda m: m["flows"][0].update(path="../outside.json"))
    elif attack == "duplicate":
        raw = rewrite_archive(candidate, extra=("manifest.json", b"{}"))
    elif attack == "extra":
        raw = rewrite_archive(candidate, extra=("flows/internal.json", b"{}"))
    elif attack == "version":
        raw = rewrite_archive(candidate, manifest_change=lambda m: m.update(schema_version=99))
    elif attack == "size":
        raw = rewrite_archive(candidate, manifest_change=lambda m: m["flows"][0].update(size=2**40))
    elif attack == "requirements":
        raw = rewrite_archive(candidate, manifest_change=lambda m: m["requirements"].update(variables=[]))
    else:
        raw = candidate.archive()
    expected = "0" * 64 if attack == "digest" else candidate.digest if attack == "requirements" else None
    with pytest.raises(ValueError, match=r"[Cc]andidate|manifest|member|Harness"):
        read_candidate(raw, expected_digest=expected)


@pytest.mark.parametrize(
    "kind", ["approval", "permission", "file", "variable", "connection", "provider", "runtime", "package"]
)
def test_preflight_rejects_incompatible_host_and_resources(kind):
    import json

    from lfx.cli.harness_artifacts import preflight_candidate
    from lfx.projects.runtime_artifacts import RuntimeCandidate

    root = definition("root")
    template = {}
    root["data"]["nodes"] = [{"id": "Agent-1", "data": {"type": "Agent", "node": {"template": template}}}]
    if kind == "approval":
        template["tool_policy"] = {"value": "ask"}
    elif kind == "permission":
        template["permission_binding"] = {"value": "{} "}
    elif kind == "file":
        template["path"] = {"type": "file", "value": ["authoring-only.pdf"]}
    elif kind == "variable":
        template["api_key"] = {"load_from_db": True, "value": "MISSING_CANDIDATE_VARIABLE"}
    elif kind == "connection":
        template["account"] = {"type": "connection_ref", "value": "malformed-reference"}
    elif kind == "provider":
        template["model"] = {"value": [{"provider": "Missing Provider"}]}
    candidate = build_candidate(root["id"], [root])
    if kind in {"runtime", "package"}:
        manifest = candidate.manifest
        if kind == "runtime":
            manifest["runtime"]["lfx"] = "0.0.0-incompatible"
        else:
            manifest["runtime"]["packages"] = ["candidate-nonexistent-package==1.0"]
        candidate = RuntimeCandidate(json.dumps(manifest).encode(), candidate.files)
    with pytest.raises(ValueError, match=r"[Cc]andidate|[Cc]onnection|[Mm]issing"):
        preflight_candidate(candidate)


def test_size_limit_is_enforced(monkeypatch):
    root = definition("root")
    monkeypatch.setitem(build_candidate.__globals__, "MAX_FLOW_BYTES", 10)
    with pytest.raises(ValueError, match="size limit"):
        build_candidate(root["id"], [root])


def test_unlisted_flow_never_falls_back_to_database():
    from types import SimpleNamespace

    from lfx.components.flow_controls.run_flow import RunFlowComponent

    root = definition("root")
    candidate = build_candidate(root["id"], [root])
    graph = Graph.from_payload(root["data"], instantiate_components=False)
    candidate.bind(graph)
    component = RunFlowComponent()
    component._vertex = SimpleNamespace(graph=graph)
    with pytest.raises(ValueError, match="not included"):
        component._frozen_flow(str(uuid4()), root["name"])


def test_sanitized_output_validation_keeps_original_review_identity():
    from lfx.projects.bindings import FlowBinding, flow_revision

    child = definition("instructions")
    source_revision = "a" * 64
    root = definition("root", child["id"])
    candidate = build_candidate(root["id"], [root, child], source_revisions={child["id"]: source_revision})
    binding = FlowBinding(flow_id=child["id"], node_id="Prompt", output_name="prompt", revision=source_revision)
    executable = candidate.execution_binding(binding)
    assert executable.revision == flow_revision(child["data"])
    assert binding.revision == source_revision
    with pytest.raises(ValueError, match="reviewed source"):
        candidate.execution_binding(binding.model_copy(update={"revision": "b" * 64}))


def test_candidate_checkpoint_requires_matching_retained_bytes():
    from lfx.graph.checkpoint.schema import GraphCheckpoint

    root = definition("root")
    candidate = build_candidate(root["id"], [root])
    graph = Graph.from_payload(root["data"], flow_id=root["id"], instantiate_components=False)
    candidate.bind(graph)
    graph.set_run_id(str(uuid4()))
    checkpoint = GraphCheckpoint.model_validate_json(graph.build_checkpoint().model_dump_json())
    assert checkpoint.candidate_digest == candidate.digest
    with pytest.raises(ValueError, match="retained Harness candidate"):
        Graph.resume_from_checkpoint(checkpoint)
    other = definition("other")
    with pytest.raises(ValueError, match="retained Harness candidate"):
        Graph.resume_from_checkpoint(checkpoint, runtime_candidate=build_candidate(other["id"], [other]))
    checkpoint.flow_payload = {"nodes": [{"id": "draft-drift"}], "edges": []}
    restored = Graph.resume_from_checkpoint(checkpoint, runtime_candidate=candidate)
    assert restored.runtime_candidate.digest == candidate.digest
    assert restored.frozen_tool_flows[root["id"]]["data"] == root["data"]
    assert not restored.vertices
    with pytest.raises(ValueError, match="legacy checkpoint"):
        Graph.resume_from_checkpoint(
            checkpoint.model_copy(update={"candidate_digest": None}), runtime_candidate=candidate
        )


def test_destination_variable_reference_replaces_provider_default(monkeypatch):
    from lfx.cli.harness_artifacts import preflight_candidate

    root = definition("root")
    root["data"]["nodes"] = [
        {
            "id": "Agent-1",
            "data": {
                "type": "Agent",
                "node": {
                    "template": {
                        "model": {"value": [{"provider": "OpenAI"}]},
                        "api_key": {"load_from_db": True, "value": "CANDIDATE_PROVIDER_KEY"},
                    }
                },
            },
        }
    ]
    monkeypatch.setenv("CANDIDATE_PROVIDER_KEY", "destination-test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    candidate = build_candidate(root["id"], [root])
    assert candidate.manifest["requirements"]["variables"] == ["CANDIDATE_PROVIDER_KEY"]
    preflight_candidate(candidate)
    with pytest.raises(ValueError, match="Missing destination"):
        preflight_candidate(candidate, no_env_fallback=True)


def test_dependency_revision_conflict_is_rejected():
    child = definition("child")
    root = definition("root", child["id"])
    root["data"]["nodes"][0]["data"]["_harness_binding"] = {"revision": "a" * 64}
    with pytest.raises(ValueError, match="conflicts with its reviewed revision"):
        build_candidate(root["id"], [root, child])


def test_skill_cannot_silently_lose_its_tools():
    from lfx.projects.skills import HarnessSkills, skill_pack_manifest
    from lfx.projects.tool_packs import ToolPackReference

    pack = ToolPackReference(project_id=uuid4(), revision="a" * 64)
    skill = skill_pack_manifest(
        uuid4(),
        "Research",
        {
            "skills": [
                {
                    "name": "research",
                    "description": "Research",
                    "instructions": "Cite sources",
                    "tool_packs": [pack.model_dump(mode="json")],
                }
            ]
        },
    )
    root = definition("root")
    root["data"]["nodes"] = [
        {
            "id": "Agent-1",
            "data": {
                "type": "Agent",
                "node": {
                    "template": {
                        "skill_bindings": {"value": HarnessSkills(packs=(skill,)).model_dump_json()},
                    }
                },
            },
        }
    ]
    with pytest.raises(ValueError, match="Tool Pack that is missing"):
        build_candidate(root["id"], [root])


def test_nested_candidate_preserves_end_user_and_ephemeral_execution():
    root = definition("root")
    candidate = build_candidate(root["id"], [root])
    parent = Graph.from_payload(root["data"], instantiate_components=False)
    child = Graph.from_payload(root["data"], instantiate_components=False)
    parent.end_user_id = "research-user"
    parent.persist_messages = False
    parent.context["request_variables"] = {"CONTEXT": "per-request"}
    candidate.inherit(parent, child)
    assert child.end_user_id == "research-user"
    assert child.persist_messages is False
    child.context["request_variables"]["CONTEXT"] = "child-only"
    assert parent.context["request_variables"]["CONTEXT"] == "per-request"
