"""Unit coverage for the LE-2020 database lock retry helper."""

import sqlite3

import pytest
from langflow.services.database.lock_retry import (
    RetryableTransactionError,
    TransactionRepairError,
    is_database_lock_error,
    run_with_lock_retry,
    sanitize_database_error,
)
from sqlalchemy.exc import IntegrityError, OperationalError


class RecordingSession:
    """Minimal stand-in that records rollbacks; the helper only ever calls rollback()."""

    def __init__(self):
        self.rollbacks = 0

    async def rollback(self):
        self.rollbacks += 1


async def test_external_repair_runs_after_rollback_and_only_once():
    """A provider repair cannot retain the failed write's transaction or repeat indefinitely."""
    session = RecordingSession()
    repairs = []
    cause = ValueError("still deployed")

    async def repair():
        assert session.rollbacks == 1
        repairs.append("repaired")

    async def operation(_attempt):
        raise TransactionRepairError(key="deployment", repair=repair, cause=cause)

    with pytest.raises(ValueError, match="still deployed"):
        await run_with_lock_retry(operation, session=session, description="deployment repair")
    assert repairs == ["repaired"]


async def test_exhausted_repair_preserves_the_original_guard_error():
    """The API must receive its guard error when there is no retry left."""
    session = RecordingSession()
    cause = ValueError("still deployed")

    async def repair():
        pytest.fail("No external repair is needed when the retry budget is exhausted")

    async def operation(_attempt):
        raise TransactionRepairError(key="deployment", repair=repair, cause=cause)

    with pytest.raises(ValueError, match="still deployed"):
        await run_with_lock_retry(operation, session=session, description="exhausted repair", attempts=1)


def test_explicit_writer_restart_uses_the_existing_lock_error_response():
    assert is_database_lock_error(RetryableTransactionError())


def make_lock_error(errorname: str = "SQLITE_BUSY_SNAPSHOT") -> OperationalError:
    original = sqlite3.OperationalError("database is locked")
    original.sqlite_errorname = errorname
    return OperationalError("DELETE FROM folder WHERE folder.id = ?", {"id": "abc"}, original)


def test_should_detect_lock_error_from_extended_result_code():
    assert is_database_lock_error(make_lock_error()) is True
    assert is_database_lock_error(make_lock_error("SQLITE_BUSY")) is True
    assert is_database_lock_error(make_lock_error("SQLITE_LOCKED")) is True


def test_should_detect_lock_error_from_message_without_error_name():
    original = sqlite3.OperationalError("database is locked")
    assert is_database_lock_error(OperationalError("stmt", {}, original)) is True


def test_should_not_treat_other_database_errors_as_lock_errors():
    assert is_database_lock_error(IntegrityError("stmt", {}, Exception("UNIQUE constraint failed"))) is False
    assert is_database_lock_error(ValueError("database is locked")) is False
    assert is_database_lock_error(None) is False


def test_should_not_inspect_sqlalchemy_bound_parameters_for_lock_text():
    constraint_error = IntegrityError(
        "UPDATE flow SET name = ?",
        {"name": "database is locked"},
        sqlite3.IntegrityError("UNIQUE constraint failed: flow.user_id, flow.name"),
    )

    assert is_database_lock_error(constraint_error) is False


def test_should_detect_lock_error_wrapped_in_another_exception():
    lock_error = make_lock_error()
    wrapper = RuntimeError("delete failed")
    wrapper.__cause__ = lock_error
    assert is_database_lock_error(wrapper) is True


def test_should_hide_sql_from_database_errors_only():
    leaky = make_lock_error()
    assert sanitize_database_error(leaky, "Could not delete the project.") == "Could not delete the project."
    assert sanitize_database_error(ValueError("plain failure"), "fallback") == "plain failure"


async def test_should_retry_until_the_operation_succeeds():
    session = RecordingSession()
    seen: list[int] = []

    async def operation(attempt: int) -> str:
        seen.append(attempt)
        if attempt < 2:
            raise make_lock_error()
        return "deleted"

    result = await run_with_lock_retry(operation, session=session, description="test", base_delay=0.001)

    assert result == "deleted"
    assert seen == [0, 1, 2]
    assert session.rollbacks == 2, "each retry must start from a rolled-back transaction"


async def test_should_retry_an_explicit_stale_lock_set_on_any_database():
    session = RecordingSession()
    seen: list[int] = []

    async def operation(attempt: int) -> str:
        seen.append(attempt)
        if attempt == 0:
            raise RetryableTransactionError
        return "locked"

    result = await run_with_lock_retry(operation, session=session, description="test", base_delay=0.001)

    assert result == "locked"
    assert seen == [0, 1]
    assert session.rollbacks == 1


async def test_should_reraise_the_last_error_when_attempts_are_exhausted():
    session = RecordingSession()

    async def always_locked(_attempt: int) -> None:
        raise make_lock_error()

    with pytest.raises(OperationalError):
        await run_with_lock_retry(always_locked, session=session, description="test", attempts=3, base_delay=0.001)

    assert session.rollbacks == 2


async def test_should_not_retry_errors_that_are_not_lock_contention():
    session = RecordingSession()
    calls = {"count": 0}

    constraint_error = IntegrityError("stmt", {}, sqlite3.IntegrityError("UNIQUE constraint failed"))

    async def failing(_attempt: int) -> None:
        calls["count"] += 1
        raise constraint_error

    with pytest.raises(IntegrityError):
        await run_with_lock_retry(failing, session=session, description="test", base_delay=0.001)

    assert calls["count"] == 1
    assert session.rollbacks == 0
