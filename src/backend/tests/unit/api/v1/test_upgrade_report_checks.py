"""An admin runs the upgrade check from the running server and the report lands in the history."""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import langflow.__main__ as langflow_main
import pytest
import typer.main
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope
from langflow.services.upgrade_reports.history import (
    MAX_REPORT_BYTES,
    UnsupportedReportFormatError,
    import_report_content,
)
from langflow.services.upgrade_reports.run import (
    DATABASE_URL_VARIABLE,
    InvalidTargetVersionError,
    _child_events,
    _redact,
    _stop,
    check_command,
    check_environment,
    check_lock,
    install_cutoff,
    parse_releases,
    parse_target_version,
    run_check,
    running_version,
)
from lfx.constants import BASE_COMPONENTS_PATH
from lfx.services.settings.base import Settings
from packaging.version import Version
from sqlmodel import select

URL = "/api/v1/upgrade-reports"
FIXTURE = Path(__file__).parent / "fixtures" / "upgrade-report-v1.json"
RUNNING = Version("1.15.0")
WEB_SETTINGS = (
    "allow_custom_components",
    "substitute_outdated_component_code",
    "block_code_interpreter_components",
    "custom_component_admin_only",
    "allow_components_paths_override",
)
DATABASE_URL = "postgresql://u:secret@h/db"  # pragma: allowlist secret


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
    assert str(parse_target_version("1.15", current=RUNNING)) == "1.15.0"


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
        "output": Path("/work/report.json"),
        "settings": settings,
        "python": "/venv/bin/python",
        "uvx": "/bin/uvx",
    }
    return check_command(**{**arguments, **overrides})


def parse_with_the_cli(command, monkeypatch):
    """What the real `upgrade-check` command makes of the arguments after its name."""
    monkeypatch.setenv(DATABASE_URL_VARIABLE, "sqlite:////data/langflow.db")
    cli = typer.main.get_command(langflow_main.app).commands["upgrade-check"]
    return cli.make_context("upgrade-check", command[command.index("upgrade-check") + 1 :]).params


def test_command_for_the_running_release_runs_this_python_without_download(monkeypatch):
    command = command_for("1.15.0", Settings())
    assert command[:4] == ["/venv/bin/python", "-m", "langflow", "upgrade-check"]
    assert "uvx" not in " ".join(command)
    params = parse_with_the_cli(command, monkeypatch)
    assert params["as_json"] is True
    assert Path(params["output"]) == Path("/work/report.json")
    assert params["database_url"] == "sqlite:////data/langflow.db"


def test_command_for_another_release_installs_it_with_uvx(monkeypatch):
    command = command_for("1.16.0", Settings(), package="langflow-base")
    assert command[: command.index("upgrade-check")] == [
        "/bin/uvx",
        "--python",
        "/venv/bin/python",
        "--from",
        "langflow-base[postgresql]==1.16.0",
        "langflow",
    ]
    assert parse_with_the_cli(command, monkeypatch)["as_json"] is True


def test_command_pins_the_installs_dependencies_to_the_releases_upload_time():
    command = command_for("1.16.0", Settings(), exclude_newer="2026-11-01T10:00:00.123456Z")
    assert command[command.index("--exclude-newer") + 1] == "2026-11-01T10:00:00.123456Z"
    assert command.index("--exclude-newer") < command.index("--from")
    assert "--exclude-newer" not in command_for("1.16.0", Settings())
    assert "--exclude-newer" not in command_for("1.15.0", Settings(), exclude_newer="2026-11-01T10:00:00Z")


def test_install_cutoff_keeps_every_file_of_the_release():
    # uv keeps only uploads strictly before the cutoff; the release's own files must stay installable.
    uploads = ["2026-11-24T07:51:59.770791Z", "2026-11-24T07:52:52.650647Z"]
    assert install_cutoff(uploads) == "2026-11-25T07:52:52Z"
    assert install_cutoff([]) is None


def test_command_leaves_the_database_url_out_of_the_argument_list():
    assert "sqlite" not in " ".join(command_for("1.16.0", Settings()))


def test_command_passes_custom_components_folders_and_leaves_out_this_releases_and_missing_ones(tmp_path, monkeypatch):
    custom_a, custom_b = tmp_path / "custom-a", tmp_path / "custom-b"
    custom_a.mkdir()
    custom_b.mkdir()
    # `langflow run` adds this default folder, which does not exist in this release.
    langflow_default = str(Path(langflow_main.__file__).parent / "components")
    settings = settings_with(
        components_path=[str(custom_a), BASE_COMPONENTS_PATH, langflow_default, str(tmp_path / "gone"), str(custom_b)]
    )
    params = parse_with_the_cli(command_for("1.15.0", settings), monkeypatch)
    assert list(params["components_path"]) == [str(custom_a), str(custom_b)]


def test_command_passes_every_server_setting_flag(monkeypatch):
    settings = settings_with(
        allow_custom_components=False,
        substitute_outdated_component_code=False,
        block_code_interpreter_components=True,
        custom_component_admin_only=False,
        allow_components_paths_override=False,
    )
    params = parse_with_the_cli(command_for("1.15.0", settings), monkeypatch)
    assert {name: params[name] for name in WEB_SETTINGS} == {
        "allow_custom_components": False,
        "substitute_outdated_component_code": False,
        "block_code_interpreter_components": True,
        "custom_component_admin_only": False,
        "allow_components_paths_override": False,
    }


def test_command_turns_default_settings_into_positive_flags(monkeypatch):
    settings = settings_with(allow_custom_components=True, block_code_interpreter_components=False)
    params = parse_with_the_cli(command_for("1.15.0", settings), monkeypatch)
    assert params["allow_custom_components"] is True
    assert params["block_code_interpreter_components"] is False


def test_environment_keeps_what_uv_and_the_check_need_and_drops_secrets(tmp_path):
    inherited = {
        "PATH": "/usr/bin",
        "HOME": "/home/langflow",
        "https_proxy": "http://proxy:3128",
        "UV_INDEX_URL": "https://mirror.example/simple",
        "UV_PUBLISH_TOKEN": "publish-only",  # pragma: allowlist secret
        "uv_publish_password": "publish-password",  # pragma: allowlist secret
        "LC_ALL": "C.UTF-8",
        "PGSSLROOTCERT": "/certs/root.pem",
        "LANGFLOW_SECRET_KEY": "server-secret",  # pragma: allowlist secret
        "OPENAI_API_KEY": "sk-test",  # pragma: allowlist secret
        "AWS_SECRET_ACCESS_KEY": "aws-secret",  # pragma: allowlist secret
        DATABASE_URL_VARIABLE: "postgresql://stale",
    }
    env = check_environment(inherited, database_url=DATABASE_URL, cache_dir=tmp_path / "cache")
    assert env == {
        "PATH": "/usr/bin",
        "HOME": "/home/langflow",
        "https_proxy": "http://proxy:3128",
        "UV_INDEX_URL": "https://mirror.example/simple",
        "LC_ALL": "C.UTF-8",
        "PGSSLROOTCERT": "/certs/root.pem",
        "UV_CACHE_DIR": str(tmp_path / "cache"),
        DATABASE_URL_VARIABLE: DATABASE_URL,
    }


def python_child(source):
    return [sys.executable, "-c", source]


async def run_child(source, output, *, timeout=30, heartbeat=10, env=None):
    redact = lambda text: _redact(text, DATABASE_URL)  # noqa: E731
    child_env = os.environ if env is None else env
    return [
        event
        async for event in _child_events(
            python_child(source), child_env, output=output, timeout=timeout, heartbeat=heartbeat, redact=redact
        )
    ]


def printed(*events):
    return "".join(f"print({json.dumps(json.dumps(event))}, flush=True);" for event in events)


async def test_child_flow_events_pass_through_and_other_lines_are_dropped(tmp_path):
    output = tmp_path / "report.json"
    output.touch()
    flow = {"event": "flow", "flow": {"status": "warn", "name": "private name"}}
    source = (
        printed(flow, {"event": "flow", "flow": {"status": "unknown"}}, ["not", "an", "event"])
        + "print('not json', flush=True)"
    )
    assert await run_child(source, output) == [{"event": "flow", "status": "warn"}]


async def test_child_error_event_passes_through_with_the_database_url_and_password_redacted(tmp_path):
    error = {"event": "error", "code": "check_failed", "message": f"cannot read {DATABASE_URL}, password secret"}
    events = await run_child(printed(error) + "raise SystemExit(2)", tmp_path / "report.json")
    assert events == [{"event": "error", "code": "check_failed", "message": "cannot read <database url>, password ***"}]


@pytest.mark.parametrize("exit_code", [1, 3])
async def test_a_child_without_a_report_explains_why_it_failed(tmp_path, exit_code):
    source = f"import sys; print('boom {DATABASE_URL} secret', file=sys.stderr); sys.exit({exit_code})"
    events = await run_child(source, tmp_path / "report.json")
    assert events == [{"event": "error", "code": "install_failed", "message": "boom <database url> ***"}]


@pytest.mark.parametrize("exit_code", [0, 1])
async def test_a_child_that_writes_a_report_and_exits_with_a_verdict_code_ends_cleanly(tmp_path, exit_code):
    output = tmp_path / "report.json"
    source = f"from pathlib import Path; Path({str(output)!r}).write_text('{{}}'); raise SystemExit({exit_code})"
    assert await run_child(source, output) == []


async def test_a_child_without_a_report_or_stderr_reports_missing_output(tmp_path):
    assert await run_child("raise SystemExit(1)", tmp_path / "report.json") == [
        {"event": "error", "code": "install_failed", "message": "The check ended without a report."}
    ]


async def test_a_child_that_does_not_finish_is_stopped_after_heartbeats_and_ends_with_a_timeout(tmp_path):
    events = await run_child("import time; time.sleep(60)", tmp_path / "report.json", timeout=0.5, heartbeat=0.1)
    assert {"event": "heartbeat"} in events
    assert [event["code"] for event in events if event["event"] == "error"] == ["timeout"]
    assert events[-1]["event"] == "error"


async def test_an_over_long_stdout_line_is_skipped_and_the_run_finishes(tmp_path):
    output = tmp_path / "report.json"
    output.touch()
    source = "print('x' * 300_000, flush=True);" + printed({"event": "flow", "flow": {"status": "ok"}})
    assert await run_child(source, output) == [{"event": "flow", "status": "ok"}]


async def test_stopping_the_checker_also_closes_its_workers_output_pipe():
    # The worker inherits stdout. Killing its parent alone leaves that pipe open.
    source = (
        "import subprocess, sys; "
        "worker = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(15)']); "
        "print('ready', flush=True); worker.wait()"
    )
    process = await asyncio.create_subprocess_exec(
        *python_child(source), stdout=asyncio.subprocess.PIPE, start_new_session=os.name == "posix"
    )
    ready = await asyncio.wait_for(process.stdout.readline(), timeout=10)
    assert ready.rstrip() == b"ready"
    await asyncio.wait_for(_stop(process), timeout=10)
    assert await asyncio.wait_for(process.stdout.read(), timeout=2) == b""


async def test_a_full_temp_directory_releases_the_check_lock(monkeypatch):
    def no_space(**_kwargs):
        msg = "no space left"
        raise OSError(msg)

    monkeypatch.setattr("langflow.services.upgrade_reports.run.tempfile.mkdtemp", no_space)
    events = [event async for event in run_check(RUNNING, current=RUNNING, package="langflow", admin_id=uuid4())]
    assert [event["code"] for event in events] == ["check_failed"]
    assert not check_lock.locked()


async def test_a_child_that_cannot_be_started_ends_with_one_error(tmp_path):
    events = [
        event
        async for event in _child_events(
            ["/nonexistent/program"],
            os.environ,
            output=tmp_path / "report.json",
            timeout=5,
            heartbeat=1,
            redact=lambda text: text,
        )
    ]
    assert events == [{"event": "error", "code": "install_failed", "message": "The check could not be started."}]


@pytest.mark.usefixtures("client")
async def test_the_shared_import_refuses_a_newer_format_and_an_oversize_report():
    async with session_scope() as session:
        newer = {**json.loads(FIXTURE.read_text()), "format_version": 2}
        with pytest.raises(UnsupportedReportFormatError):
            await import_report_content(session, json.dumps(newer).encode(), uuid4())
        with pytest.raises(ValueError, match="size limit"):
            await import_report_content(session, b" " * (MAX_REPORT_BYTES + 1), uuid4())


@pytest.mark.parametrize(
    ("missing_flows", "errors", "expected"),
    [
        (True, [], True),
        (False, [], False),
        (False, [{"kind": "scan", "status": "fail", "message": "scan stopped"}], True),
    ],
)
async def test_the_shared_import_stores_a_valid_report(client, admin_headers, missing_flows, errors, expected):
    document = json.loads(FIXTURE.read_bytes())
    if not missing_flows:
        document["summary"]["flows"] = {"ok": 0, "warn": 1, "fail": 0}
    document["errors"] = errors
    async with session_scope() as session:
        user = (await session.exec(select(User).where(User.username == "check-admin"))).one()
        row, incomplete = await import_report_content(session, json.dumps(document).encode(), user.id)
    history = (await client.get(URL, headers=admin_headers)).json()
    assert [item["id"] for item in history["items"]] == [str(row.id)]
    assert history["items"][0]["incomplete"] is incomplete is expected


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
    assert events[0] == {"event": "started", "target_version": target, "download": False, "total": 2}
    # The total is what the page's progress bar counts toward.
    assert [e for e in events if e["event"] == "flow"] == [{"event": "flow", "status": "ok"}] * 2
    assert events[-1]["event"] == "imported", events[-1]
    assert events[-1]["flows"] == {"ok": 2, "warn": 0, "fail": 0}
    assert events[-1]["incomplete"] is False
    assert [e["event"] for e in events].count("imported") + [e["event"] for e in events].count("error") == 1
    report_id = events[-1]["report_id"]
    history = (await client.get(URL, headers=admin_headers)).json()
    assert [item["id"] for item in history["items"]] == [report_id]
    assert history["items"][0]["target_version"] == target
    assert not check_lock.locked()
