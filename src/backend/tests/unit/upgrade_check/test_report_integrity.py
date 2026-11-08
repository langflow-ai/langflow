"""Report output must preserve its source and identify it without credentials."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.upgrade_check.command import (
    CheckError,
    _needs_action,
    _report_destination,
    _source_message,
    _write_report,
)
from langflow.upgrade_check.reader import read_only_connection
from langflow.upgrade_check.source import SOURCE_IDENTITY_ADAPTER, identity_for_source
from pydantic import ValidationError

from tests.unit.upgrade_check.test_command import _events, _upgrade_check
from tests.unit.upgrade_check.test_engine import _add_flow, _hard_flow
from tests.unit.upgrade_check.test_reader import _load, _url


@pytest.mark.parametrize("alias", ["same_file", "symlink", "hardlink", "sqlite_query"])
def test_report_output_cannot_alias_its_sqlite_source(alias, tmp_path):
    source = _load("1.13.0", tmp_path)
    output = source if alias in {"same_file", "sqlite_query"} else tmp_path / "report.json"
    if alias == "symlink":
        output.symlink_to(source)
    elif alias == "hardlink":
        output.hardlink_to(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    url = _url(source) + ("?uri=true&mode=ro" if alias == "sqlite_query" else "")

    result = _upgrade_check("--database-url", url, "--output", output, "--json")

    assert result.returncode == 2, result.stderr
    [error] = _events(result)
    assert (error["event"], error["code"]) == ("error", "output_aliases_source")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    with sqlite3.connect(source) as connection:
        assert connection.execute("SELECT count(*) FROM flow").fetchone()[0] == 2


def test_source_connection_errors_do_not_echo_credentials():
    credentials = (
        "postgresql://private-user:private-password@db.example.test/app?token=private-token"  # pragma: allowlist secret
    )

    message = _source_message(RuntimeError(f"connection failed for {credentials}"))

    for value in (credentials, "private-user", "private-password", "private-token"):
        assert value not in message


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
@pytest.mark.parametrize("alias", ["direct", "symlink", "hardlink"])
def test_report_destination_refuses_sqlite_journal_aliases(suffix, alias, tmp_path):
    source = _load("1.13.0", tmp_path)
    journal = Path(f"{source}{suffix}")
    journal.write_bytes(b"source journal fixture")
    output = journal if alias == "direct" else tmp_path / "report.json"
    if alias == "symlink":
        output.symlink_to(journal)
    elif alias == "hardlink":
        output.hardlink_to(journal)
    before = source.read_bytes(), journal.read_bytes()

    with pytest.raises(CheckError) as caught:
        _report_destination(_url(source), str(output))

    assert caught.value.code == "output_aliases_source"
    assert (source.read_bytes(), journal.read_bytes()) == before


def test_report_output_cannot_replace_a_live_wal_file(tmp_path):
    source = _load("1.13.0", tmp_path)
    writer = sqlite3.connect(source)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("UPDATE flow SET name = name || ' saved'")
        writer.commit()
        protected = [source, Path(f"{source}-wal"), Path(f"{source}-shm")]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}

        result = _upgrade_check("--database-url", _url(source), "--output", f"{source}-wal", "--json")

        assert result.returncode == 2, result.stderr
        [error] = _events(result)
        assert error["code"] == "output_aliases_source"
        assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected} == before
        assert writer.execute("SELECT count(*) FROM flow").fetchone()[0] == 2
    finally:
        writer.close()


def test_sqlite_identity_is_stable_and_distinguishes_copies_without_query_credentials(tmp_path):
    first = _load("1.13.0", tmp_path)
    second = tmp_path / "another-installation.db"
    second.write_bytes(first.read_bytes())
    alias = tmp_path / "selected-source.db"
    alias.symlink_to(first)
    identities = []
    urls = [_url(first) + "?token=old-private-token", _url(alias) + "?token=new-private-token", _url(second)]
    for url in urls:
        with read_only_connection(url) as connection:
            identities.append(identity_for_source(url, connection))

    assert identities[0] == identities[1]
    assert identities[0].sha256 != identities[2].sha256
    assert identities[0].locator.path == str(first.resolve())
    serialized = json.dumps([identity.model_dump() for identity in identities])
    assert "old-private-token" not in serialized
    assert "new-private-token" not in serialized
    assert "sqlite:///" not in serialized
    for identity in identities:
        assert SOURCE_IDENTITY_ADAPTER.validate_python(identity.model_dump()) == identity
    changed = deepcopy(identities[0].model_dump())
    changed["locator"]["path"] = str(second)
    with pytest.raises(ValidationError, match="fingerprint"):
        SOURCE_IDENTITY_ADAPTER.validate_python(changed)
    changed = identities[0].model_dump() | {"password": "private-password"}
    with pytest.raises(ValidationError, match="Extra inputs"):
        SOURCE_IDENTITY_ADAPTER.validate_python(changed)


def test_postgres_identity_distinguishes_selected_schemas_without_exposing_options():
    url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("LANGFLOW_TEST_POSTGRES_URL is not set")
    schemas = [f"identity_{uuid4().hex}" for _ in range(2)]
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        for schema in schemas:
            connection.execute(sa.schema.CreateSchema(schema))
    identities = []
    try:
        for schema in schemas:
            selected = sa.make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
            for user, password, token in [
                ("old-user", "old-password", "old-token"),
                ("new-user", "new-password", "new-token"),
            ]:
                supplied = selected.set(username=user, password=password).update_query_dict({"token": token})
                with read_only_connection(selected.render_as_string(hide_password=False)) as connection:
                    identities.append(identity_for_source(supplied.render_as_string(hide_password=False), connection))
        assert identities[0] == identities[1]
        assert identities[2] == identities[3]
        assert identities[0].sha256 != identities[2].sha256
        serialized = json.dumps([identity.model_dump() for identity in identities])
        for secret in [
            *schemas,
            "old-user",
            "old-password",
            "old-token",
            "new-user",
            "new-password",
            "new-token",
            "-csearch_path",
            "postgresql://",
        ]:
            assert secret not in serialized
    finally:
        with admin.begin() as connection:
            for schema in schemas:
                connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()


def test_identity_models_import_without_the_dry_run_engine():
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import sys; import langflow.upgrade_check.source; "
            "assert 'langflow.upgrade_check.engine' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("as_json", [False, True], ids=["text", "json"])
def test_warning_only_cli_result_requires_review(as_json, tmp_path):
    source = _load("1.13.0", tmp_path)
    _add_flow(source, "Customized flow", data=json.dumps(_hard_flow("v1.12.6", "customized.json")), is_component=0)

    result = _upgrade_check("--database-url", _url(source), *(["--json"] if as_json else []))

    assert result.returncode == 1, result.stderr
    if as_json:
        report = _events(result)[-1]["report"]
        assert report["summary"]["flows"]["warn"] == 1
        assert report["summary"]["flows"]["fail"] == 0
    else:
        assert "Review the warnings before upgrading" in result.stdout
        assert "Nothing blocks the upgrade" not in result.stdout


def test_warning_counts_as_action_without_a_confirmed_failure():
    assert _needs_action({"summary": {"flows": {"ok": 0, "warn": 1, "fail": 0}}, "errors": []})


def test_output_alias_created_after_preflight_is_refused_without_truncation(tmp_path):
    source = _load("1.13.0", tmp_path)
    output = tmp_path / "report.json"
    destination = _report_destination(_url(source), str(output))
    before = source.read_bytes()
    output.hardlink_to(source)

    with pytest.raises(CheckError):
        _write_report(_url(source), destination, {"report": "replacement"})

    assert source.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == [source.name, output.name]


def test_cli_reports_distinguish_identical_sources_without_query_tokens(tmp_path):
    first = _load("1.13.0", tmp_path)
    second = tmp_path / "another-installation.db"
    second.write_bytes(first.read_bytes())
    reports = []
    for number, database in enumerate((first, second)):
        output = tmp_path / f"report-{number}.json"
        url = _url(database) + f"?token=private-query-token-{number}"
        before = hashlib.sha256(database.read_bytes()).hexdigest()

        result = _upgrade_check("--database-url", url, "--output", output, "--json")

        assert result.returncode == 0, result.stderr
        report = _events(result)[-1]["report"]
        assert json.loads(output.read_text()) == report
        assert url not in result.stdout
        assert "private-query-token" not in result.stdout
        assert "private-query-token" not in output.read_text()
        SOURCE_IDENTITY_ADAPTER.validate_python(report["source"]["identity"])
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before
        reports.append(report)
    assert reports[0]["source"]["counts"] == reports[1]["source"]["counts"]
    assert reports[0]["source"]["alembic_revision"] == reports[1]["source"]["alembic_revision"]
    assert reports[0]["source"]["identity"]["sha256"] != reports[1]["source"]["identity"]["sha256"]


@pytest.mark.parametrize("parent_kind", ["missing", "file", "directory_output"])
def test_report_output_path_is_rejected_before_reading_the_source(parent_kind, tmp_path):
    missing_source = tmp_path / "missing.db"
    parent = tmp_path / "report-folder"
    if parent_kind == "file":
        parent.write_text("not a folder")
    elif parent_kind == "directory_output":
        parent.mkdir()
    output = parent if parent_kind == "directory_output" else parent / "report.json"

    result = _upgrade_check("--database-url", _url(missing_source), "--output", output, "--json")

    assert result.returncode == 2, result.stderr
    [error] = _events(result)
    assert (error["event"], error["code"]) == ("error", "output_unwritable")
    assert not missing_source.exists()


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM handlers and SIGKILL require POSIX")
def test_interrupted_cli_reaps_a_child_that_ignores_termination(monkeypatch):
    import signal

    from langflow.__main__ import upgrade_check

    child = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-u",
            "-c",
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready'); time.sleep(60)",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    original_wait = child.wait
    original_kill = child.kill
    killed = False

    def interrupt(*_args):
        raise KeyboardInterrupt

    def kill():
        nonlocal killed
        killed = True
        original_kill()

    def bounded_wait(timeout=None):
        if timeout is None and not killed:
            msg = "cleanup must bound the wait before killing the child"
            raise AssertionError(msg)
        return original_wait(timeout=min(timeout, 0.1) if timeout is not None else None)

    try:
        assert child.stdout.readline().strip() == "ready"
        monkeypatch.setattr(child, "communicate", interrupt)
        monkeypatch.setattr(child, "wait", bounded_wait)
        monkeypatch.setattr(child, "kill", kill)
        monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
        with pytest.raises(KeyboardInterrupt):
            upgrade_check(
                database_url="sqlite:////unused.db",
                components_path=[],
                allow_custom_components=True,
                substitute_outdated_component_code=True,
                block_code_interpreter_components=False,
                custom_component_admin_only=False,
                allow_components_paths_override=True,
                as_json=True,
                output=None,
            )
        assert killed
        assert child.returncode == -signal.SIGKILL
    finally:
        if child.poll() is None:
            original_kill()
        original_wait(timeout=5)
        child.stdout.close()
