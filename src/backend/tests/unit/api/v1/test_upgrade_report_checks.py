"""An admin runs the upgrade check from the running server and the report lands in the history."""

import json
import sys
from pathlib import Path

import langflow.__main__ as langflow_main
import pytest
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope
from langflow.services.upgrade_reports.run import (
    InvalidTargetVersionError,
    check_command,
    check_lock,
    parse_releases,
    parse_target_version,
    running_version,
)
from lfx.constants import BASE_COMPONENTS_PATH
from lfx.services.settings.base import Settings
from packaging.version import Version

URL = "/api/v1/upgrade-reports"
RUNNING = Version("1.15.0")


@pytest.fixture
async def admin_headers(client):
    async with session_scope() as session:
        session.add(
            User(
                username="check-admin",
                password=get_auth_service().get_password_hash("testpassword"),
                is_active=True,
                is_superuser=True,
            )
        )
    response = await client.post(
        "/api/v1/login",
        data={"username": "check-admin", "password": "testpassword"},  # pragma: allowlist secret
    )
    assert response.status_code == 200
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def events_of(response):
    return [json.loads(block) for block in response.text.split("\n\n") if block.strip()]


@pytest.mark.parametrize("raw", ["1.15.0; rm -rf /", "https://example.com/langflow.whl", "1.15.0 --index-url x", ""])
def test_target_version_rejects_anything_that_is_not_a_version(raw):
    with pytest.raises(InvalidTargetVersionError):
        parse_target_version(raw, current=RUNNING)


@pytest.mark.parametrize(
    "raw",
    ["1.13.9", "1.15.0rc1", "1.16.0.dev1", "1.16.0a2", "1.14.2", "1!2.0.0", "1.16.0+local", "9" * 100],
)
def test_target_version_rejects_old_pre_release_and_older_than_running(raw):
    with pytest.raises(InvalidTargetVersionError):
        parse_target_version(raw, current=RUNNING)


def test_target_version_is_rebuilt_from_the_parsed_version():
    assert str(parse_target_version(" 1.16.1 ", current=RUNNING)) == "1.16.1"
    assert parse_target_version("1.15.0", current=RUNNING) == RUNNING


def test_releases_keep_final_installable_newer_versions_newest_first():
    pypi = {
        "releases": {
            "1.14.0": [{"yanked": False}],
            "1.15.0": [{"yanked": False}],
            "1.15.1": [{"yanked": False}, {"yanked": True}],
            "1.16.0": [{"yanked": True}, {"yanked": True}],
            "1.16.0rc1": [{"yanked": False}],
            "1.17.0.dev3": [{"yanked": False}],
            "1.17.0": [],
            "not-a-version": [{"yanked": False}],
            "1.20.0": [{}],
            "1.2.0": [{"yanked": False}],
        }
    }
    assert parse_releases(pypi, current=RUNNING) == ["1.20.0", "1.15.1"]
    assert parse_releases(pypi, current=RUNNING, limit=1) == ["1.20.0"]


@pytest.mark.parametrize("pypi", [{}, {"releases": []}, []])
def test_releases_refuse_an_answer_without_releases(pypi):
    with pytest.raises(ValueError, match="no releases"):
        parse_releases(pypi, current=RUNNING)


def settings_with(**values):
    # Settings reads its fields from the environment, so a value is set on the instance.
    settings = Settings()
    for name, value in values.items():
        setattr(settings, name, value)
    return settings


def command_for(target, settings, **overrides):
    arguments = {
        "target": Version(target),
        "current": RUNNING,
        "package": "langflow",
        "database_url": "sqlite:////data/langflow.db",
        "output": "/work/report.json",
        "settings": settings,
        "python": "/venv/bin/python",
        "uvx": "/bin/uvx",
    }
    return check_command(**{**arguments, **overrides})


def test_command_for_the_running_release_runs_this_python_without_download():
    command = command_for("1.15.0", Settings())
    assert command[:5] == ["/venv/bin/python", "-m", "langflow", "upgrade-check", "--database-url"]
    assert command[5:9] == ["sqlite:////data/langflow.db", "--json", "--output", "/work/report.json"]
    assert "uvx" not in " ".join(command)


def test_command_for_another_release_installs_it_with_uvx():
    command = command_for("1.16.0", Settings(), package="langflow-base")
    assert command[:7] == [
        "/bin/uvx",
        "--python",
        "/venv/bin/python",
        "--from",
        "langflow-base[postgresql]==1.16.0",
        "langflow",
        "upgrade-check",
    ]


def test_command_passes_custom_components_folders_and_leaves_out_this_releases_and_missing_ones(tmp_path):
    custom_a, custom_b = tmp_path / "custom-a", tmp_path / "custom-b"
    custom_a.mkdir()
    custom_b.mkdir()
    # `langflow run` adds this default folder, which does not exist in this release.
    langflow_default = str(Path(langflow_main.__file__).parent / "components")
    settings = settings_with(
        components_path=[str(custom_a), BASE_COMPONENTS_PATH, langflow_default, str(tmp_path / "gone"), str(custom_b)]
    )
    command = command_for("1.15.0", settings)
    assert [command[i + 1] for i, value in enumerate(command) if value == "--components-path"] == [
        str(custom_a),
        str(custom_b),
    ]


def test_command_passes_every_server_setting_flag():
    settings = settings_with(
        allow_custom_components=False,
        substitute_outdated_component_code=False,
        block_code_interpreter_components=True,
        custom_component_admin_only=False,
        allow_components_paths_override=False,
    )
    command = command_for("1.15.0", settings)
    for flag in (
        "--no-allow-custom-components",
        "--no-substitute-outdated-component-code",
        "--block-code-interpreter-components",
        "--no-custom-component-admin-only",
        "--no-allow-components-paths-override",
    ):
        assert flag in command


def test_command_turns_default_settings_into_positive_flags():
    command = command_for(
        "1.15.0", settings_with(allow_custom_components=True, block_code_interpreter_components=False)
    )
    assert "--allow-custom-components" in command
    assert "--no-block-code-interpreter-components" in command


async def test_releases_and_checks_require_admin(client, logged_in_headers):
    for headers in ({}, logged_in_headers):
        assert (await client.get(f"{URL}/checks/releases", headers=headers)).status_code in {401, 403}
        response = await client.post(f"{URL}/checks", json={"target_version": "1.15.0"}, headers=headers)
        assert response.status_code in {401, 403}


@pytest.mark.parametrize("target", ["1.15.0; rm -rf /", "1.13.9", "1.99.0rc1", "0.0.1"])
async def test_invalid_target_is_refused_before_streaming(client, admin_headers, target):
    response = await client.post(f"{URL}/checks", json={"target_version": target}, headers=admin_headers)
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "invalid_target_version"}


async def test_a_second_check_is_refused_while_one_runs(client, admin_headers):
    await check_lock.acquire()
    try:
        response = await client.post(
            f"{URL}/checks", json={"target_version": str(running_version())}, headers=admin_headers
        )
    finally:
        check_lock.release()
    assert response.status_code == 409
    assert response.json()["detail"] == {"code": "check_running"}


async def test_check_of_the_running_release_imports_a_report(client, admin_headers):
    for name in ("first", "second"):
        created = await client.post(
            "/api/v1/flows/", json={"name": name, "data": {"nodes": [], "edges": []}}, headers=admin_headers
        )
        assert created.status_code == 201, created.text
    target = str(running_version())
    response = await client.post(f"{URL}/checks", json={"target_version": target}, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = events_of(response)
    assert events[0] == {"event": "started", "target_version": target, "download": False, "total": 2}, sys.version
    # The total is what the page's progress bar counts toward.
    assert [e for e in events if e["event"] == "flow"] == [{"event": "flow", "status": "ok"}] * 2
    assert events[-1]["event"] == "imported", events[-1]
    assert events[-1]["flows"] == {"ok": 2, "warn": 0, "fail": 0}
    assert [e["event"] for e in events].count("imported") + [e["event"] for e in events].count("error") == 1
    report_id = events[-1]["report_id"]
    history = (await client.get(URL, headers=admin_headers)).json()
    assert [item["id"] for item in history["items"]] == [report_id]
    assert history["items"][0]["target_version"] == target
    assert not check_lock.locked()
