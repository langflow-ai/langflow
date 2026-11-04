"""Imported checker reports stay inert, private to admins, and exportable."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from langflow.services.database.models.upgrade_report import UpgradeReport
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope
from sqlmodel import select

URL = "/api/v1/upgrade-reports"
FIXTURE = Path(__file__).parent / "fixtures" / "upgrade-report-v1.json"


@pytest.fixture
async def admin_headers(client):
    async with session_scope() as session:
        session.add(
            User(
                username="report-admin",
                password=get_auth_service().get_password_hash("testpassword"),
                is_active=True,
                is_superuser=True,
            )
        )
    response = await client.post(
        "/api/v1/login",
        data={"username": "report-admin", "password": "testpassword"},  # pragma: allowlist secret
    )
    assert response.status_code == 200
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_history_detail_and_export_retain_exact_document(client, admin_headers):
    document = json.loads(FIXTURE.read_text())
    document["future_metadata"] = {"labels": ["preserve me"], "unknown": None}
    document["flows"][0]["labels"] = ["Production"]
    original = json.dumps(document, ensure_ascii=False, indent=4) + "\n\n"
    response = await client.post(URL, content=original, headers=admin_headers)
    assert response.status_code == 201, response.text
    stored = response.json()
    assert stored["document"] == document
    assert (stored["flow_count"], stored["warning_count"], stored["failing_count"]) == (4, 1, 0)
    report_id = stored["id"]
    history = (await client.get(URL, headers=admin_headers)).json()
    assert history["total"] == 1
    assert history["items"][0]["id"] == report_id
    assert "document" not in history["items"][0]
    detail = await client.get(f"{URL}/{report_id}", headers=admin_headers)
    assert detail.json()["document"] == document
    export = await client.get(f"{URL}/{report_id}/export", headers=admin_headers)
    assert export.content == original.encode()
    assert export.headers["cache-control"] == "no-store"
    async with session_scope() as session:
        [persisted] = (await session.exec(select(UpgradeReport))).all()
        assert persisted.document_json == original


async def test_all_endpoints_require_admin_authorization(client, logged_in_headers, admin_headers):
    response = await client.post(URL, content=FIXTURE.read_bytes(), headers=admin_headers)
    report_id = response.json()["id"]
    for headers in ({}, logged_in_headers):
        for path in (URL, f"{URL}/{report_id}", f"{URL}/{report_id}/export"):
            assert (await client.get(path, headers=headers)).status_code in {401, 403}
        assert (await client.post(URL, content=FIXTURE.read_bytes(), headers=headers)).status_code in {401, 403}


@pytest.mark.parametrize(
    "corruption", ["version", "identity", "dialect", "count", "timezone", "duplicate", "non_object"]
)
async def test_invalid_reports_leave_history_unchanged(client, admin_headers, corruption):
    document = json.loads(FIXTURE.read_text())
    if corruption == "version":
        document["format_version"] = 2
    elif corruption == "identity":
        document["source"]["identity"]["sha256"] = "0" * 64
    elif corruption == "dialect":
        document["source"]["dialect"] = "postgresql"
    elif corruption == "count":
        document["summary"]["flows"]["warn"] = True
    elif corruption == "timezone":
        document["generated_at"] = "2026-11-04T13:14:15+00:99"
    elif corruption == "duplicate":
        document["flows"].append(deepcopy(document["flows"][0]))
    else:
        document = []
    response = await client.post(URL, json=document, headers=admin_headers)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "invalid_upgrade_report"
    assert (await client.get(URL, headers=admin_headers)).json()["total"] == 0


@pytest.mark.parametrize("content", [b"not JSON", b'{"format_version":NaN}', b"\xff"])
async def test_invalid_json_and_encoding_are_rejected(client, admin_headers, content):
    assert (await client.post(URL, content=content, headers=admin_headers)).status_code == 422
    assert (await client.get(URL, headers=admin_headers)).json()["total"] == 0


async def test_old_report_unknown_identity_and_metadata_stay_unknown(client, admin_headers):
    document = json.loads(FIXTURE.read_text())
    del document["source"]["identity"]
    document["flows"][0]["last_edited_at"] = None
    response = await client.post(URL, json=document, headers=admin_headers)
    assert response.status_code == 201, response.text
    assert response.json()["source_identity"] is None
    assert response.json()["document"] == document


async def test_pagination_target_filter_and_missing_report(client, admin_headers):
    document = json.loads(FIXTURE.read_text())
    await client.post(URL, json=document, headers=admin_headers)
    document["target"]["langflow"] = "1.14.1"
    newest = await client.post(URL, json=document, headers=admin_headers)
    result = (await client.get(URL, params={"limit": 1}, headers=admin_headers)).json()
    assert result["total"] == 2
    assert [entry["id"] for entry in result["items"]] == [newest.json()["id"]]
    second = (await client.get(URL, params={"offset": 1, "limit": 1}, headers=admin_headers)).json()
    assert second["items"][0]["target_version"] == "1.14.0"
    filtered = (await client.get(URL, params={"target_version": "1.14.1"}, headers=admin_headers)).json()
    assert filtered["total"] == 1
    assert (await client.get(URL, params={"limit": 101}, headers=admin_headers)).status_code == 422
    assert (await client.get(f"{URL}/{uuid4()}", headers=admin_headers)).status_code == 404


async def test_admin_reports_work_during_database_maintenance(client, logged_in_headers, admin_headers):
    assert (await client.post("/api/v1/maintenance/on", json={}, headers=admin_headers)).status_code == 200
    response = await client.post(URL, content=FIXTURE.read_bytes(), headers=admin_headers)
    assert response.status_code == 201, response.text
    assert (await client.get(f"{URL}/{response.json()['id']}", headers=admin_headers)).status_code == 200
    assert (await client.post(URL, content=FIXTURE.read_bytes(), headers=logged_in_headers)).status_code == 503


def test_report_api_does_not_import_checker_engine():
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import sys; import langflow.api.v1.upgrade_reports; "
            "assert 'langflow.upgrade_check.engine' not in sys.modules; "
            "assert 'langflow.upgrade_check.command' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


async def test_oversize_upload_is_rejected_before_json_parsing(client, admin_headers):
    from langflow.services.upgrade_reports.history import MAX_REPORT_BYTES

    response = await client.post(URL, content=b" " * (MAX_REPORT_BYTES + 1), headers=admin_headers)
    assert response.status_code == 413
    assert (await client.get(URL, headers=admin_headers)).json()["total"] == 0


async def test_repair_outcomes_share_the_callers_transaction_and_leave_export_immutable(client, admin_headers):
    from uuid import UUID

    from langflow.services.upgrade_reports.history import record_repair_result, require_report

    imported = (await client.post(URL, content=FIXTURE.read_bytes(), headers=admin_headers)).json()
    report_id = UUID(imported["id"])
    result = {"flow_id": str(uuid4()), "status": "updated", "recovery_version_id": str(uuid4()), "reason_codes": []}
    async with session_scope() as session:
        report = await session.get(UpgradeReport, report_id)
        await record_repair_result(
            session, report_id=report_id, actor_id=report.created_by, target_sha256="a" * 64, result=result
        )
        await session.rollback()
    assert (await client.get(f"{URL}/{report_id}/repairs", headers=admin_headers)).json()["total"] == 0
    async with session_scope() as session:
        report = await session.get(UpgradeReport, report_id)
        await record_repair_result(
            session, report_id=report_id, actor_id=report.created_by, target_sha256="a" * 64, result=result
        )
        await session.commit()
    history = (await client.get(f"{URL}/{report_id}/repairs", headers=admin_headers)).json()
    assert history["total"] == 1
    assert history["items"][0]["result"] == result
    assert (await client.get(f"{URL}/{report_id}/export", headers=admin_headers)).content == FIXTURE.read_bytes()
    assert (await client.get(f"{URL}/{report_id}/repairs")).status_code in {401, 403}
    async with session_scope() as session:
        with pytest.raises(ValueError, match="not found"):
            await require_report(session, uuid4())
        assert (
            await record_repair_result(session, report_id=None, actor_id=uuid4(), target_sha256="a" * 64, result=result)
            is None
        )
