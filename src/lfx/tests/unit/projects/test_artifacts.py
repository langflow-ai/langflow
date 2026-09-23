import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from lfx.components.data_source.record_source import RecordSourceComponent
from lfx.components.files_and_knowledge.sourced_report import SourcedReportComponent
from lfx.graph.graph.base import Graph
from lfx.projects.artifacts import ArtifactExecution, SourcedReport, SourceRecord, store_report
from lfx.schema.data import Data
from lfx.services.storage.local import LocalStorageService


@pytest.fixture
def storage(tmp_path, monkeypatch):
    storage = LocalStorageService(None, SimpleNamespace(settings=SimpleNamespace(config_dir=str(tmp_path))))
    monkeypatch.setattr("lfx.services.deps.get_storage_service", lambda: storage)
    monkeypatch.setattr("lfx.components.files_and_knowledge.sourced_report.get_storage_service", lambda: storage)
    return storage


def source(**overrides):
    return SourceRecord(
        **{
            "uri": "https://example.org/study",
            "title": "Offline study fixture",
            "content": "The offline fixture contains three observations. This is test evidence, not live research.",
            **overrides,
        }
    )


def report(**overrides):
    evidence = source()
    return SourcedReport(
        **{
            "title": "Test research",
            "markdown": f"The fixture has three observations. [@{evidence.id}]",
            "sources": (evidence,),
            "execution": ArtifactExecution(flow_id=uuid4(), run_id=uuid4(), node_id="SourcedReport-test"),
            **overrides,
        }
    )


def test_evidence_identity_tracks_captured_content_not_capture_time():
    first = source()
    repeat = source(captured_at=first.captured_at + timedelta(days=1))
    assert first.id == repeat.id
    assert source(content="The page changed.").id != first.id
    assert source(uri="https://example.org/other").id != first.id
    assert SourceRecord.model_validate_json(first.model_dump_json()) == first
    with pytest.raises(ValueError, match="does not match"):
        SourceRecord.model_validate({**first.model_dump(), "content": "Replaced evidence"})


@pytest.mark.parametrize(
    "overrides",
    [
        {"content": ""},
        {"content": "   "},
        {"unavailable_reason": "request failed"},
        {"availability": "unavailable"},
        {"availability": "unavailable", "content": "", "unavailable_reason": ""},
        {"captured_at": datetime(2026, 1, 1)},  # noqa: DTZ001 - deliberately reject naive capture times
    ],
)
def test_invalid_evidence_cannot_claim_success(overrides):
    with pytest.raises(ValueError, match="validation error"):
        source(**overrides)


def test_citation_resolution_distinguishes_membership_availability_and_claim_support():
    available = source()
    unavailable = source(availability="unavailable", content="", unavailable_reason="Source server timed out.")
    result = report(
        markdown=f"A claim [@{available.id}] and [@missing] and [@{unavailable.id}]. Again [@{available.id}].",
        sources=(available, unavailable, available),
    )
    assert [item.status for item in result.citations] == ["resolved", "missing", "unavailable"]
    assert len(result.sources) == 2
    assert result.claim_support == "not_evaluated"
    restored = SourcedReport.model_validate_json(result.model_dump_json())
    assert restored.citations == result.citations
    with pytest.raises(ValueError, match="missing or unavailable"):
        restored.require_resolved_citations()
    rendered = restored.render_markdown()
    assert "Evidence missing" in rendered
    assert "Evidence unavailable: Source server timed out." in rendered
    assert "Claim support has not been evaluated" in rendered
    assert available.content not in rendered  # Raw evidence stays separate from generated prose.


@pytest.mark.parametrize("markdown", ["No citations.", "A claim [@].", "A claim [@bad id].", "[@" + "x" * 200 + "]"])
def test_unresolved_or_absent_markers_cannot_pass_publication(markdown):
    with pytest.raises(ValueError, match=r"citation|evidence"):
        report(markdown=markdown).require_resolved_citations()


def test_resolved_does_not_mean_supported_and_cannot_be_supplied_as_a_claim_evaluation():
    evidence = source()
    result = report(markdown=f"An intentionally unsupported assertion. [@{evidence.id}]")
    result.require_resolved_citations()
    assert result.claim_support == "not_evaluated"
    with pytest.raises(ValueError, match="claim_support"):
        SourcedReport.model_validate({**result.model_dump(), "claim_support": "supported"})


@pytest.mark.parametrize("uri", ["javascript:alert(1)", "data:text/html,bad", "https://user:secret@example.org/a"])
def test_evidence_locations_are_preserved_but_unsafe_web_links_are_not_rendered(uri):
    evidence = source(uri=uri, title="[unsafe](javascript:alert(1)) <script>")
    result = report(sources=(evidence,), markdown=f"A claim. [@{evidence.id}]")
    rendered = result.render_markdown()
    assert "[unsafe](javascript:" not in rendered
    assert "<script>" not in rendered
    assert uri in result.model_dump_json()
    assert f"]({uri})" not in rendered


async def test_stored_report_survives_reload_and_concurrent_saves_do_not_overwrite(storage):
    evidence = source(content="Captured evidence stays complete, including non-ASCII text: ação.\n" * 2000)
    original = report(sources=(evidence,), markdown=f"A claim. [@{evidence.id}]")
    first, second = await asyncio.gather(store_report(original, storage), store_report(original, storage))
    assert first.report.id != second.report.id
    flow_id = str(original.execution.flow_id)
    reloaded = SourcedReport.model_validate_json(await storage.get_file(flow_id, first.record_name))
    assert reloaded == first.report
    assert reloaded.sources[0].content == original.sources[0].content
    assert reloaded.execution.run_id == original.execution.run_id
    assert (await storage.get_file(flow_id, first.markdown_name)).decode() == reloaded.render_markdown()
    assert set(await storage.list_files(flow_id)) == {
        first.markdown_name,
        first.record_name,
        second.markdown_name,
        second.record_name,
    }


async def test_failed_record_write_cleans_its_partial_files_and_preserves_prior_artifact(storage, monkeypatch):
    original = report()
    saved = await store_report(original, storage)
    save_file = storage.save_file

    async def fail_record(flow_id, file_name, data):
        await save_file(flow_id, file_name, data)
        if file_name.endswith(".json"):
            msg = "Injected write failure after partial persistence"
            raise OSError(msg)

    monkeypatch.setattr(storage, "save_file", fail_record)
    with pytest.raises(OSError, match="Injected"):
        await store_report(original, storage)
    assert set(await storage.list_files(str(original.execution.flow_id))) == {saved.markdown_name, saved.record_name}


def graph_report(*, markdown=None, require_resolved=True, flow_id=None):
    evidence = source()
    capture = RecordSourceComponent()
    capture.set(uri=evidence.uri, title=evidence.title, content=evidence.content)
    output = SourcedReportComponent()
    output.set(
        title="Offline report",
        report=markdown or f"The fixture has three observations. [@{evidence.id}]",
        sources=capture.record_source,
        require_resolved=require_resolved,
    )
    graph = Graph(capture, output, flow_id=flow_id or str(uuid4()))
    return graph, output._id


async def test_real_graph_captures_evidence_and_persists_inspectable_canonical_artifact(storage):
    from lfx.schema.schema import build_output_logs

    graph, output_id = graph_report()
    results = [result async for result in graph.async_start()]
    assert all(getattr(result, "valid", True) for result in results)
    vertex = graph.get_vertex(output_id)
    result = vertex.custom_component.get_output("artifact").value
    assert isinstance(result, Data)
    canonical = SourcedReport.model_validate(result.data["artifact"])
    assert str(canonical.execution.run_id) == graph.run_id
    assert canonical.execution.node_id == output_id
    assert canonical.sources[0].content == source().content
    canonical.require_resolved_citations()
    record_name = result.data["files"][1].split("/")[1]
    assert SourcedReport.model_validate_json(await storage.get_file(graph.flow_id, record_name)) == canonical
    preview = build_output_logs(vertex, (vertex.custom_component,))["artifact"]
    assert preview["message"]["artifact"]["id"] == str(canonical.id)


async def test_unresolved_graph_does_not_save_but_explicit_draft_retains_missing_evidence(storage):
    graph, _ = graph_report(markdown="A claim [@missing].")
    with pytest.raises(Exception, match="missing or unavailable"):
        _ = [result async for result in graph.async_start()]
    assert not await storage.data_dir.joinpath(graph.flow_id).exists()
    draft, output_id = graph_report(markdown="A claim [@missing].", require_resolved=False)
    _ = [result async for result in draft.async_start()]
    result = draft.get_vertex(output_id).custom_component.get_output("artifact").value
    assert result.data["citations"] == [{"source_id": "missing", "status": "missing"}]
    assert "Evidence missing" in result.data["text"]


async def test_artifact_uses_canonical_source_flow_storage_namespace(storage):
    graph, output_id = graph_report()
    graph.source_flow_id = str(uuid4())
    _ = [result async for result in graph.async_start()]
    artifact = graph.get_vertex(output_id).custom_component.get_output("artifact").value.data
    assert artifact["artifact"]["execution"]["flow_id"] == graph.source_flow_id
    assert all(path.startswith(graph.source_flow_id + "/") for path in artifact["files"])
    assert not await storage.data_dir.joinpath(graph.flow_id).exists()


def test_record_source_can_terminate_a_callable_tool_flow():
    from lfx.components.input_output.chat import ChatInput
    from lfx.projects.tools import prepare_tool_template

    request = ChatInput()
    request.set(should_store_message=False)
    capture = RecordSourceComponent()
    capture.set(uri="https://example.org/fixture", title="Tool fixture", content=request.message_response)
    graph = Graph(request, capture, flow_id=str(uuid4()))
    payload = graph.dump(name="Evidence tool")
    # Palette templates populate field_order; Graph.dump from Python instances does not.
    for node in payload["data"]["nodes"]:
        if node["data"]["type"] == "ChatInput":
            node["data"]["node"]["field_order"] = [item.name for item in ChatInput.inputs]
    template = prepare_tool_template({**payload, "id": graph.flow_id})
    assert template["template"]["flow_id_selected"]["value"] == graph.flow_id
    assert any(item.get("tool_mode") for item in template["template"].values() if isinstance(item, dict))
