"""Tests for the startup warning about psycopg's pure-Python libpq wrapper.

``warn_if_psycopg_pure_python`` logs one WARNING per process when a PostgreSQL
URL uses psycopg and ``psycopg.pq.__impl__ == "python"``, and stays quiet
otherwise (SQLite, other drivers, psycopg not imported, compiled implementation,
or ``PSYCOPG_IMPL=python`` chosen on purpose).
"""

import sys
import types
from unittest.mock import MagicMock

import pytest
from langflow.services.database import service as db_service
from langflow.services.database.service import warn_if_psycopg_pure_python

PG_URL = "postgresql+psycopg://langflow@db.internal:5432/langflow"


def _fake_psycopg(impl: str) -> types.ModuleType:
    module = types.ModuleType("psycopg")
    module.__version__ = "3.3.4"
    module.pq = types.SimpleNamespace(__impl__=impl)
    return module


@pytest.fixture
def mock_logger(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(db_service, "logger", logger)
    monkeypatch.setattr(db_service, "_psycopg_pure_python_warned", False)
    monkeypatch.delenv("PSYCOPG_IMPL", raising=False)
    return logger


def test_warns_once_for_pure_python_impl(mock_logger, monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", _fake_psycopg("python"))

    assert warn_if_psycopg_pure_python(PG_URL) is True
    assert warn_if_psycopg_pure_python(PG_URL) is False

    mock_logger.warning.assert_called_once()
    message = mock_logger.warning.call_args.args[0]
    assert "pure-Python" in message
    assert 'psycopg[binary]==3.3.4"' in message
    assert 'psycopg[c]==3.3.4"' in message
    assert "db.internal" not in message  # never echoes the database URL


@pytest.mark.parametrize("url", [PG_URL, "postgresql+psycopg_async://localhost/langflow"])
def test_warns_for_psycopg_driver_names(mock_logger, monkeypatch, url):
    monkeypatch.setitem(sys.modules, "psycopg", _fake_psycopg("python"))

    assert warn_if_psycopg_pure_python(url) is True
    mock_logger.warning.assert_called_once()


@pytest.mark.parametrize("impl", ["binary", "c"])
def test_quiet_for_compiled_impl(mock_logger, monkeypatch, impl):
    monkeypatch.setitem(sys.modules, "psycopg", _fake_psycopg(impl))

    assert warn_if_psycopg_pure_python(PG_URL) is False
    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+aiosqlite:///./langflow.db",
        "sqlite://",
        "postgresql+asyncpg://localhost/langflow",
        "postgresql+psycopg2://localhost/langflow",
        "not a url",
    ],
)
def test_quiet_for_non_psycopg_urls(mock_logger, monkeypatch, url):
    monkeypatch.setitem(sys.modules, "psycopg", _fake_psycopg("python"))

    assert warn_if_psycopg_pure_python(url) is False
    mock_logger.warning.assert_not_called()


def test_quiet_when_psycopg_not_imported(mock_logger, monkeypatch):
    monkeypatch.delitem(sys.modules, "psycopg", raising=False)

    assert warn_if_psycopg_pure_python(PG_URL) is False
    mock_logger.warning.assert_not_called()
    assert "psycopg" not in sys.modules  # the check must not import psycopg itself


@pytest.mark.parametrize("value", ["python", " Python "])
def test_quiet_when_pure_python_is_forced(mock_logger, monkeypatch, value):
    monkeypatch.setitem(sys.modules, "psycopg", _fake_psycopg("python"))
    monkeypatch.setenv("PSYCOPG_IMPL", value)

    assert warn_if_psycopg_pure_python(PG_URL) is False
    mock_logger.warning.assert_not_called()


async def test_initialize_database_runs_the_check(monkeypatch):
    from langflow.services.database import utils as db_utils

    calls = []
    monkeypatch.setattr(db_service, "warn_if_psycopg_pure_python", calls.append)
    monkeypatch.setattr(db_service, "check_sqlite_database_path", MagicMock(side_effect=RuntimeError("stop")))
    database_service = MagicMock()
    database_service.database_url = PG_URL

    async def _noop():
        return None

    database_service.ensure_postgresql_version = _noop
    monkeypatch.setattr("langflow.services.deps.get_db_service", lambda: database_service)

    with pytest.raises(RuntimeError, match="stop"):
        await db_utils.initialize_database()

    assert calls == [PG_URL]
