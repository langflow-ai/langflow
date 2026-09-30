"""Memory management for lfx with dynamic dispatch.

Routes memory operations to either the full langflow implementation (when
langflow is installed AND a real database service is registered) or the lfx
stub implementation (standalone / noop DB).

Dispatch is evaluated at call time, not import time, because the database
service is typically registered *after* this module is first imported (e.g.,
from Component class definitions loaded before graph setup). An import-time
decision can't distinguish "langflow is importable" from "a real DB is wired",
and picking the langflow backend with a NoopDatabaseService yields silent
no-op inserts followed by spurious "Message with id X not found" errors on
update.
"""

from __future__ import annotations

from typing import Any

from lfx.utils.langflow_utils import has_langflow_db_backend


def _impl():
    if has_langflow_db_backend():
        from langflow import memory as impl
    else:
        from lfx.memory import stubs as impl
    return impl


def aadd_messages(*args: Any, **kwargs: Any):
    return _impl().aadd_messages(*args, **kwargs)


def aadd_messagetables(*args: Any, **kwargs: Any):
    return _impl().aadd_messagetables(*args, **kwargs)


def add_messages(*args: Any, **kwargs: Any):
    return _impl().add_messages(*args, **kwargs)


def adelete_messages(*args: Any, **kwargs: Any):
    return _impl().adelete_messages(*args, **kwargs)


def aget_messages(*args: Any, **kwargs: Any):
    return _impl().aget_messages(*args, **kwargs)


def astore_message(*args: Any, **kwargs: Any):
    return _impl().astore_message(*args, **kwargs)


def aupdate_messages(*args: Any, **kwargs: Any):
    return _impl().aupdate_messages(*args, **kwargs)


def delete_message(*args: Any, **kwargs: Any):
    return _impl().delete_message(*args, **kwargs)


def delete_messages(*args: Any, **kwargs: Any):
    return _impl().delete_messages(*args, **kwargs)


def get_messages(*args: Any, **kwargs: Any):
    return _impl().get_messages(*args, **kwargs)


def store_message(*args: Any, **kwargs: Any):
    return _impl().store_message(*args, **kwargs)


__all__ = [
    "aadd_messages",
    "aadd_messagetables",
    "add_messages",
    "adelete_messages",
    "aget_messages",
    "astore_message",
    "aupdate_messages",
    "delete_message",
    "delete_messages",
    "get_messages",
    "store_message",
]
