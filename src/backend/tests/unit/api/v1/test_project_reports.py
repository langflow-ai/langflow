from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.services.deps import get_storage_service
from lfx.projects.artifacts import ArtifactExecution, SourcedReport, SourceRecord, store_report

from tests.unit.api.v1.test_project_config_write_through import create_flow, create_project


@pytest.fixture
async def saved_project_report(client, logged_in_headers, active_user):
    project_id = await create_project(client, logged_in_headers, name="Report reader")
    flow_id = await create_flow(active_user, folder_id=project_id, data={"nodes": [], "edges": []})
    source = SourceRecord(uri="fixture://study", title="Offline study", content="Original evidence.\n" * 10000)
    report = SourcedReport(
        title="Sourced findings",
        markdown=f"The fixture contains evidence. [@{source.id}]",
        execution=ArtifactExecution(flow_id=flow_id, run_id=uuid4(), node_id="report"),
        sources=(source,),
    )
    storage = get_storage_service()
    saved = await store_report(report, storage)
    return project_id, flow_id, saved, storage


async def test_project_reports_list_full_evidence_and_both_downloads(client, logged_in_headers, saved_project_report):
    project_id, flow_id, saved, storage = saved_project_report
    url = f"/api/v1/projects/{project_id}/reports"
    response = await client.get(url, headers=logged_in_headers)
    assert response.status_code == 200, response.text
    summary = response.json()["items"][0]
    assert summary["id"] == str(saved.report.id)
    assert summary["source_count"] == summary["citation_count"] == 1
    assert summary["citations_resolved"] is True
    assert summary["claim_support"] == "not_evaluated"
    assert "Original evidence" not in response.text
    assert len(response.content) < 3000
    detail = f"{url}/{flow_id}/{saved.report.id}"
    response = await client.get(detail, headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert SourcedReport.model_validate(response.json()) == saved.report
    assert len(response.json()["sources"][0]["content"].encode()) > 128_000
    # Downloading derives from the canonical record, independently of a removed Markdown copy.
    await storage.delete_file(flow_id, saved.markdown_name)
    for file_format in ("json", "markdown"):
        response = await client.get(f"{detail}/download/{file_format}", headers=logged_in_headers)
        assert response.status_code == 200, response.text
        assert response.headers["content-disposition"].startswith("attachment;")
        if file_format == "json":
            assert SourcedReport.model_validate_json(response.content) == saved.report
        else:
            assert response.text == saved.report.render_markdown()
    # The previous artifact implementation's files remain discoverable without an index.
    await storage.delete_file(flow_id, f"report-{saved.report.id}.summary.json")
    assert (await client.get(url, headers=logged_in_headers)).json()["items"] == [summary]


async def test_project_reports_do_not_cross_user_or_project_boundaries(
    client,
    logged_in_headers,
    saved_project_report,
    user_two_api_key,
    active_user,
):
    project_id, flow_id, saved, _ = saved_project_report
    url = f"/api/v1/projects/{project_id}/reports"
    detail = f"{url}/{flow_id}/{saved.report.id}"
    client.cookies.clear()
    for endpoint in (url, detail, f"{detail}/download/json", f"{detail}/download/markdown"):
        denied = await client.get(endpoint, headers={"x-api-key": user_two_api_key})
        assert denied.status_code == 404
        assert saved.report.title not in denied.text
        anonymous = await client.get(endpoint)
        assert anonymous.status_code in {401, 403}
    other_project = await create_project(client, logged_in_headers, name="Other project")
    other_flow = await create_flow(
        active_user, folder_id=other_project, data={"nodes": [], "edges": []}, name="Other flow"
    )
    for wrong_url in (
        f"/api/v1/projects/{other_project}/reports/{flow_id}/{saved.report.id}",
        f"{url}/{other_flow}/{saved.report.id}",
    ):
        assert (await client.get(wrong_url, headers=logged_in_headers)).status_code == 404
    assert (await client.get(f"/api/v1/projects/{other_project}/reports", headers=logged_in_headers)).json()[
        "items"
    ] == []


async def test_project_report_rejects_invalid_records_and_bad_pagination(
    client, logged_in_headers, saved_project_report
):
    project_id, flow_id, saved, storage = saved_project_report
    url = f"/api/v1/projects/{project_id}/reports"
    for query in ("limit=0", "limit=101", "cursor=not-a-cursor"):
        assert (await client.get(f"{url}?{query}", headers=logged_in_headers)).status_code == 422
    detail = f"{url}/{flow_id}/{saved.report.id}"
    changed = saved.report.model_dump(mode="json")
    changed["sources"][0]["content"] = "Changed source text"
    import json

    await storage.save_file(flow_id, saved.record_name, json.dumps(changed).encode())
    for endpoint in (detail, f"{detail}/download/json"):
        response = await client.get(endpoint, headers=logged_in_headers)
        assert response.status_code == 409
        assert "Changed source text" not in response.text
    await storage.delete_file(flow_id, saved.record_name)
    assert (await client.get(detail, headers=logged_in_headers)).status_code == 404
    assert (await client.get(url, headers=logged_in_headers)).json()["items"] == []


async def test_report_routes_honor_project_and_flow_policy(
    client, logged_in_headers, saved_project_report, monkeypatch
):
    project_id, flow_id, saved, _ = saved_project_report
    module = "langflow.api.v1.project_reports"
    calls = []

    async def deny_project(user, action, **scope):  # noqa: ARG001
        calls.append(scope)
        raise HTTPException(status_code=403)

    monkeypatch.setattr(f"{module}.ensure_project_permission", deny_project)
    url = f"/api/v1/projects/{project_id}/reports"
    assert (await client.get(url, headers=logged_in_headers)).status_code == 404
    assert calls[-1]["project_id"] == UUID(project_id)

    async def allow_project(*args, **kwargs):
        pass

    async def hide_flows(user, **kwargs):  # noqa: ARG001
        assert len(kwargs["candidates"]) == 1
        return []

    async def deny_flow(user, action, **scope):  # noqa: ARG001
        calls.append(scope)
        raise HTTPException(status_code=403)

    monkeypatch.setattr(f"{module}.ensure_project_permission", allow_project)
    monkeypatch.setattr(f"{module}.filter_visible_resources", hide_flows)
    monkeypatch.setattr(f"{module}.ensure_flow_permission", deny_flow)
    assert (await client.get(url, headers=logged_in_headers)).json()["items"] == []
    response = await client.get(f"{url}/{flow_id}/{saved.report.id}", headers=logged_in_headers)
    assert response.status_code == 404
    assert calls[-1]["flow_id"] == UUID(flow_id)
