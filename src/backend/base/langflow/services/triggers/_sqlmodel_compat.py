"""Compatibility helpers around SQLModel quirks.

SQLModel's ``AsyncSession.execute`` is the right choice — and the only
choice — for ``text()`` raw SQL and for ``update()`` / ``delete()``
constructs. The library still raises a ``DeprecationWarning`` on
every ``execute`` call urging the caller to use ``exec`` instead, even
when ``exec`` does not accept the statement type. The warning is
informational and unrelated to anything actionable on our end.

This module centralises a tight context manager that silences only
that specific warning, so every trigger module can wrap its raw-SQL
``execute`` calls without each one re-implementing the suppression.

The filter is narrow on purpose: scoped to the SQLModel module path
so any other ``DeprecationWarning`` from somewhere else still
surfaces.
"""

from __future__ import annotations

import warnings
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def suppress_sqlmodel_exec_warning() -> Iterator[None]:
    """Silence SQLModel's 'use exec()' nudge for the wrapped block.

    Use around the few legitimate ``session.execute(...)`` calls we
    have (raw SQL via :func:`sqlalchemy.text`, or ORM
    ``update()`` / ``delete()`` constructs that :meth:`AsyncSession.exec`
    explicitly does not accept).
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            module=r"sqlmodel\.ext\.asyncio\.session",
        )
        yield
