from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from lfx.projects.artifact_store import list_reports, read_report
from lfx.projects.artifacts import ArtifactExecution, ReportSummary, SourceRecord, store_report

from tests.unit.projects.test_artifacts import report
from tests.unit.projects.test_artifacts import storage as storage_fixture

artifact_storage = storage_fixture


async def test_listing_uses_small_records_and_paginates_all_authorized_flows(artifact_storage, monkeypatch):
    first_flow, second_flow = uuid4(), uuid4()
    created = datetime(2026, 9, 15, tzinfo=timezone.utc)
    saved = []
    for index in range(4):
        value = report(
            created_at=created + timedelta(minutes=index),
            execution=ArtifactExecution(
                flow_id=first_flow if index % 2 else second_flow,
                run_id=uuid4(),
                node_id="report",
            ),
        )
        saved.append(await store_report(value, artifact_storage))
    get_file = artifact_storage.get_file

    async def metadata_only(flow_id, file_name):
        assert file_name.endswith(".summary.json"), "Listing loaded a full source record"
        return await get_file(flow_id, file_name)

    monkeypatch.setattr(artifact_storage, "get_file", metadata_only)
    first = await list_reports(artifact_storage, [first_flow, second_flow, first_flow], limit=2)
    await store_report(
        report(
            created_at=created + timedelta(hours=1),
            execution=ArtifactExecution(
                flow_id=first_flow,
                run_id=uuid4(),
                node_id="report",
            ),
        ),
        artifact_storage,
    )
    second = await list_reports(artifact_storage, [first_flow, second_flow], limit=2, cursor=first.next_cursor)
    assert [item.id for item in (*first.items, *second.items)] == [item.report.id for item in reversed(saved)]
    assert second.next_cursor is None
    assert first.unavailable_count == second.unavailable_count == 0
    assert first.items[0].citations_resolved
    assert first.items[0].claim_support == "not_evaluated"


async def test_legacy_records_remain_visible_and_detail_retains_full_source_text(artifact_storage):
    value = report(sources=(SourceRecord(uri="fixture://long", title="Long evidence", content="exact text\n" * 20000),))
    saved = await store_report(value, artifact_storage)
    flow_id = value.execution.flow_id
    await artifact_storage.delete_file(str(flow_id), f"report-{saved.report.id}.summary.json")
    page = await list_reports(artifact_storage, [flow_id])
    assert page.items == (ReportSummary.from_report(saved.report),)
    loaded = await read_report(artifact_storage, flow_id, saved.report.id)
    assert loaded.sources[0].content == value.sources[0].content
    assert not page.items[0].citations_resolved


async def test_incomplete_and_corrupt_records_do_not_become_completed_reports(artifact_storage):
    saved = await store_report(report(), artifact_storage)
    flow_id = saved.report.execution.flow_id
    await artifact_storage.delete_file(str(flow_id), saved.record_name)
    assert not (await list_reports(artifact_storage, [flow_id])).items
    await artifact_storage.save_file(str(flow_id), saved.record_name, b"{broken")
    await artifact_storage.delete_file(str(flow_id), f"report-{saved.report.id}.summary.json")
    page = await list_reports(artifact_storage, [flow_id])
    assert not page.items
    assert page.unavailable_count == 1
    with pytest.raises(ValueError, match="Invalid JSON"):
        await read_report(artifact_storage, flow_id, saved.report.id)


async def test_report_identity_and_flow_namespace_must_match(artifact_storage):
    saved = await store_report(report(), artifact_storage)
    other_flow = uuid4()
    await artifact_storage.save_file(str(other_flow), saved.record_name, saved.report.model_dump_json().encode())
    with pytest.raises(ValueError, match="storage location"):
        await read_report(artifact_storage, other_flow, saved.report.id)
    page = await list_reports(artifact_storage, [other_flow])
    assert not page.items
    assert page.unavailable_count == 1


@pytest.mark.parametrize("cursor", ["not-base64", "e30=", "W10=", "WyJvbmx5Il0="])
async def test_invalid_cursor_is_rejected(artifact_storage, cursor):
    with pytest.raises(ValueError, match="cursor"):
        await list_reports(artifact_storage, [], cursor=cursor)
