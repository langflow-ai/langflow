"""Source-only libpq inputs survive isolation without reaching component callbacks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.upgrade_check import command, reader
from langflow.upgrade_check.engine import TargetSettings
from langflow.upgrade_check.isolation import child_environment, resolve_input_paths, source_connection_context


def test_postgres_connection_inputs_are_private_and_not_in_the_child_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "original"))
    monkeypatch.setenv("PGUSER", "fixture-reader")
    monkeypatch.setenv("PGPASSWORD", "fixture-only-password")
    monkeypatch.setenv("PGSERVICEFILE", "service.conf")
    monkeypatch.setenv("KRB5CCNAME", "FILE:fixture-credential-cache")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-provider-key")
    options = {"database_url": "postgresql://127.0.0.1:15476/fixture", "settings": {"components_path": []}}
    original = deepcopy(options)

    selected = resolve_input_paths(options)

    private = selected["_source_connection"]
    assert private["working_directory"] == str(tmp_path)
    assert private["environment"]["HOME"] == str(tmp_path / "original")
    assert private["environment"]["PGPASSWORD"] == "fixture-only-password"  # pragma: allowlist secret
    assert private["environment"]["PGSERVICEFILE"] == "service.conf"
    assert private["environment"]["KRB5CCNAME"] == "FILE:fixture-credential-cache"
    assert "OPENAI_API_KEY" not in private["environment"]
    isolated = child_environment(str(tmp_path / "isolated"), os.environ)
    assert not any(name.startswith("PG") or name == "KRB5CCNAME" for name in isolated)
    assert "OPENAI_API_KEY" not in isolated
    assert options == original


@pytest.mark.parametrize("fail", [False, True])
def test_private_connection_context_restores_the_clean_environment_and_directory(monkeypatch, tmp_path, fail):
    source, isolated = tmp_path / "source", tmp_path / "isolated"
    source.mkdir()
    isolated.mkdir()
    monkeypatch.chdir(isolated)
    with patch.dict(os.environ, child_environment(str(isolated), os.environ), clear=True):
        before = dict(os.environ)
        inputs = {
            "environment": {"HOME": str(source), "PGPASSWORD": "fixture-password"},
            "working_directory": str(source),
        }
        try:
            with source_connection_context(inputs):
                assert os.environ["PGPASSWORD"] == "fixture-password"  # pragma: allowlist secret
                assert Path.cwd() == source
                if fail:
                    message = "synthetic source refusal"
                    raise RuntimeError(message)
        except RuntimeError:
            assert fail
        assert dict(os.environ) == before
        assert Path.cwd() == isolated


def test_private_connection_inputs_cannot_add_provider_credentials(tmp_path):
    before = dict(os.environ)
    with (
        pytest.raises(ValueError, match="invalid private source"),
        source_connection_context({"environment": {"OPENAI_API_KEY": "synthetic"}, "working_directory": str(tmp_path)}),
    ):
        pytest.fail("invalid inputs entered the source phase")
    assert dict(os.environ) == before


@pytest.mark.parametrize(
    "configuration",
    ["environment", "default_passfile", "relative_passfile", "default_service", "relative_service", "url_precedence"],
)
def test_native_postgres_source_inputs_are_removed_before_callbacks(monkeypatch, tmp_path, configuration):
    raw = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("set LANGFLOW_TEST_POSTGRES_URL")
    pytest.importorskip("psycopg")
    admin_url = sa.make_url(raw).set(drivername="postgresql+psycopg")
    admin = sa.create_engine(admin_url)
    schema = f"source_auth_{uuid4().hex}"
    source, isolated = tmp_path / "source", tmp_path / "isolated"
    source.mkdir()
    isolated.mkdir()
    monkeypatch.chdir(source)
    for name in list(os.environ):
        if name.startswith(("PG", "KRB5_")) or name == "KRB5CCNAME":
            monkeypatch.delenv(name)
    monkeypatch.setenv("HOME", str(source))
    monkeypatch.setenv("PGUSER", admin_url.username)
    monkeypatch.setenv("PGDATABASE", admin_url.database)
    monkeypatch.setenv("PGSSLMODE", "disable")
    monkeypatch.setenv("PGGSSENCMODE", "disable")
    monkeypatch.setenv("KRB5CCNAME", "FILE:synthetic-cache")
    password = admin_url.password or f"fixture-{uuid4()}"
    tls = source / ".postgresql" / "root.crt"
    tls.parent.mkdir()
    tls.write_text("synthetic TLS path fixture, not used with sslmode=disable")
    paths = [tls]
    if configuration == "environment":
        monkeypatch.setenv("PGSSLROOTCERT", ".postgresql/root.crt")
    monkeypatch.setenv("PGPASSWORD", password)
    if configuration in {"default_passfile", "relative_passfile"}:
        path = source / (".pgpass" if configuration == "default_passfile" else "passwords")
        path.write_text(f"{admin_url.host}:{admin_url.port}:{admin_url.database}:{admin_url.username}:{password}\n")
        path.chmod(0o600)
        paths.append(path)
        monkeypatch.delenv("PGPASSWORD")
        if configuration == "relative_passfile":
            monkeypatch.setenv("PGPASSFILE", path.name)
    if configuration in {"default_service", "relative_service"}:
        path = source / (".pg_service.conf" if configuration == "default_service" else "services.conf")
        path.write_text(f"[fixture]\nuser={admin_url.username}\ndbname={admin_url.database}\npassword={password}\n")
        paths.append(path)
        monkeypatch.setenv("PGSERVICE", "fixture")
        monkeypatch.setenv("PGPASSWORD", "environment-must-not-override-service")
        if configuration == "relative_service":
            monkeypatch.setenv("PGSERVICEFILE", path.name)
    url = sa.URL.create(
        "postgresql+psycopg",
        host=admin_url.host,
        port=admin_url.port,
        query={"options": f"-csearch_path={schema}", "connect_timeout": "2"},
    )
    if configuration == "url_precedence":
        url = url.set(username=admin_url.username, password=password, database=admin_url.database)
        monkeypatch.setenv("PGUSER", "must-not-select-this-role")
        monkeypatch.setenv("PGDATABASE", "must-not-select-this-database")
        monkeypatch.setenv("PGPASSWORD", "must-not-select-this-password")
        monkeypatch.setenv("PGHOST", "synthetic.invalid")
        monkeypatch.setenv("PGPORT", "1")
    before = {path: path.read_bytes() for path in paths}
    options = {
        "database_url": url.render_as_string(hide_password=False),
        "settings": asdict(TargetSettings()),
        "json": True,
        "output": None,
    }
    selected = resolve_input_paths(options)
    private = selected.pop("_source_connection")
    observed = []

    def on_connect(_dialect, _record, _args, _params):
        assert os.environ["KRB5CCNAME"] == "FILE:synthetic-cache"
        assert os.environ["PGSSLMODE"] == "disable"
        assert (Path.home() / ".postgresql/root.crt").read_bytes() == before[tls]

    def discover(**_kwargs):
        assert not any(name.startswith("PG") or name == "KRB5CCNAME" for name in os.environ)
        assert os.environ["HOME"] == str(isolated)
        assert Path.cwd() == isolated
        observed.append("clean")
        return {}

    original_open = command.open_source
    from contextlib import contextmanager

    @contextmanager
    def open_selected(database_url):
        with original_open(database_url) as database:
            assert database.connection.connection.driver_connection.info.password == password
            yield database

    try:
        with admin.begin() as connection:
            connection.execute(sa.schema.CreateSchema(schema))
            connection.exec_driver_sql(f'SET search_path TO "{schema}"')
            connection.exec_driver_sql('CREATE TABLE "user" (id uuid, username text, is_superuser boolean)')
            connection.exec_driver_sql("CREATE TABLE folder (id uuid, name text, user_id uuid)")
            connection.exec_driver_sql(
                "CREATE TABLE flow (id uuid, name text, data json, user_id uuid, folder_id uuid, "
                "is_component boolean, updated_at timestamptz)"
            )
            for _ in range(3):
                connection.exec_driver_sql(
                    "INSERT INTO flow (id, name, data, is_component) VALUES (%s, 'fixture', %s, false)",
                    (uuid4(), json.dumps({"nodes": [], "edges": []})),
                )
        monkeypatch.setattr(command, "load_upgrade_registry", discover)
        monkeypatch.setattr(command, "open_source", open_selected)
        monkeypatch.setattr(reader, "_ROWS_PER_PAGE", 1)
        monkeypatch.chdir(isolated)
        sa.event.listen(sa.engine.Engine, "do_connect", on_connect)
        with patch.dict(os.environ, child_environment(str(isolated), os.environ), clear=True):
            report, _ = command.run(selected, source_connection=private)
        if configuration == "environment":
            script = (
                "import os; from langflow.upgrade_check import command; "
                "command.load_upgrade_registry = lambda **kwargs: {} "
                "if not any(key.startswith('PG') or key == 'KRB5CCNAME' for key in os.environ) "
                "else (_ for _ in ()).throw(AssertionError('source environment leaked')); "
                "raise SystemExit(command.main())"
            )
            argv = [sys.executable, "-c", script]
            assert password not in json.dumps(argv)
            result = subprocess.run(  # noqa: S603 -- trusted inert callback, native disposable source only
                argv,
                input=json.dumps({**selected, "_source_connection": private}),
                env=child_environment(str(isolated), os.environ),
                cwd=isolated,
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
            assert result.returncode == 0, result.stderr
            assert password not in result.stdout + result.stderr
            events = [json.loads(line) for line in result.stdout.splitlines()]
            assert events[-1]["event"] == "report"
            assert events[-1]["report"]["summary"]["flows"]["ok"] == 3
        assert observed == ["clean"]
        assert report["summary"]["flows"]["ok"] == 3
        assert password not in json.dumps(report)
        assert {path: path.read_bytes() for path in paths} == before
    finally:
        sa.event.remove(sa.engine.Engine, "do_connect", on_connect)
        with admin.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()
