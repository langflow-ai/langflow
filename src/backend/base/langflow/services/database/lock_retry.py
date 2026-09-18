"""Recovery helpers for transient database write-lock contention.

SQLite serializes writers, and under WAL a transaction that has already read
cannot be upgraded to a writer once another connection has committed: SQLite
answers ``SQLITE_BUSY_SNAPSHOT`` (message: "database is locked") *immediately*
and deliberately does not invoke the busy handler, because waiting could never
resolve a stale snapshot. ``busy_timeout`` therefore has no effect on this
class of failure — the only valid recovery is to end the transaction and run it
again against a fresh snapshot, which is what :func:`run_with_lock_retry` does.

PostgreSQL lock, deadlock and serialization failures also restart the complete
transaction. Callers may also raise
``RetryableTransactionError`` after a preliminary identifier set changes while
they acquire the repository's documented cross-entity lock order.  That
explicit signal is safe to replay on every supported database because the
failed attempt is rolled back before the next canonical read.
"""

from __future__ import annotations

import asyncio
import random
import sqlite3
from typing import TYPE_CHECKING, TypeVar

from lfx.log.logger import logger
from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

DEFAULT_LOCK_RETRY_ATTEMPTS = 8
DEFAULT_LOCK_RETRY_BASE_DELAY = 0.02
MAX_LOCK_RETRY_DELAY = 0.75

# sqlite3 exposes the extended result code by name from Python 3.11 on; the
# message check keeps older interpreters and non-extended codes covered.
_SQLITE_LOCK_ERROR_NAMES = frozenset(
    {
        "SQLITE_BUSY",
        "SQLITE_BUSY_SNAPSHOT",
        "SQLITE_BUSY_RECOVERY",
        "SQLITE_BUSY_TIMEOUT",
        "SQLITE_LOCKED",
        "SQLITE_LOCKED_SHAREDCACHE",
    }
)
_SQLITE_LOCK_MESSAGES = ("database is locked", "database table is locked")


class RetryableTransactionError(Exception):
    """Mark a transaction whose canonical lock set changed during acquisition."""


class TransactionRepairError(RetryableTransactionError):
    """Request one external repair after rollback, before replaying the whole write."""

    def __init__(self, *, key: str, repair: Callable[[], Awaitable[None]], cause: Exception) -> None:
        super().__init__(str(cause))
        self.key = key
        self.repair = repair
        self.cause = cause


def is_database_lock_error(exc: BaseException | None) -> bool:
    """Recognize driver lock/deadlock/serialization codes, never SQL parameter text."""
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, RetryableTransactionError) and not isinstance(exc, TransactionRepairError):
            return True
        error_name = getattr(exc, "sqlite_errorname", None)
        if error_name in _SQLITE_LOCK_ERROR_NAMES:
            return True
        if (getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)) in {"40001", "40P01", "55P03"}:
            return True
        # SQLAlchemy's wrapper text contains the SQL statement and bound
        # parameters. Inspect only the underlying SQLite operational error so
        # user data containing "database is locked" cannot trigger retries.
        if isinstance(exc, sqlite3.OperationalError):
            message = str(exc).lower()
            if any(marker in message for marker in _SQLITE_LOCK_MESSAGES):
                return True
        exc = getattr(exc, "orig", None) or exc.__cause__
    return False


def sanitize_database_error(exc: BaseException, fallback: str) -> str:
    """Return a client-safe message for *exc*.

    SQLAlchemy's ``str()`` embeds the failing statement, the table name and the
    bound parameters, so it must never reach an API consumer.
    """
    if isinstance(exc, SQLAlchemyError):
        return fallback
    return str(exc)


async def run_with_lock_retry(
    operation: Callable[[int], Awaitable[T]],
    *,
    session: AsyncSession,
    description: str,
    attempts: int = DEFAULT_LOCK_RETRY_ATTEMPTS,
    base_delay: float = DEFAULT_LOCK_RETRY_BASE_DELAY,
) -> T:
    """Run *operation* until it succeeds, retrying only transient lock failures.

    *operation* receives the zero-based attempt number and must be safe to run
    again from scratch: every retry starts a brand new transaction, so state
    read or written by a failed attempt is gone and has to be re-established.

    The last attempt's error propagates unchanged so callers can map an
    exhausted retry budget to their own response.
    """
    last_attempt = attempts - 1
    repaired: set[str] = set()
    for attempt in range(attempts):
        try:
            return await operation(attempt)
        except Exception as exc:
            if isinstance(exc, TransactionRepairError) and (exc.key in repaired or attempt == last_attempt):
                raise exc.cause from exc
            retryable = isinstance(exc, RetryableTransactionError) or is_database_lock_error(exc)
            if attempt == last_attempt or not retryable:
                raise
            # The snapshot is stale: roll the transaction back so the retry
            # reads current data instead of failing on the same conflict.
            await session.rollback()
            if isinstance(exc, TransactionRepairError):
                await exc.repair()
                repaired.add(exc.key)
                continue
            delay = min(base_delay * (2**attempt), MAX_LOCK_RETRY_DELAY)
            # Jitter keeps concurrent losers from colliding again in lockstep.
            await asyncio.sleep(delay * (0.5 + random.random()))  # noqa: S311
            await logger.adebug(
                "Transaction contention on %s, retrying (attempt %s/%s)", description, attempt + 2, attempts
            )
    msg = "unreachable: the retry loop either returns or raises"
    raise AssertionError(msg)
