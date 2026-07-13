"""Injectable KB helper callbacks registered by the host.

Memory-base helpers must not import ``langflow.api``. The host registers the
concrete KB helper classes/functions during bootstrap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

_KB_STORAGE_HELPER: Any = None
_KB_ANALYSIS_HELPER: Any = None
_KB_INGESTION_HELPER: Any = None
_CHUNK_TEXT_FOR_INGESTION: Callable[..., Any] | None = None


def set_kb_helpers(
    *,
    storage_helper: Any = None,
    analysis_helper: Any = None,
    ingestion_helper: Any = None,
    chunk_text_for_ingestion: Callable[..., Any] | None = None,
) -> None:
    """Register host-owned KB helper implementations."""
    global _KB_STORAGE_HELPER, _KB_ANALYSIS_HELPER, _KB_INGESTION_HELPER, _CHUNK_TEXT_FOR_INGESTION
    if storage_helper is not None:
        _KB_STORAGE_HELPER = storage_helper
    if analysis_helper is not None:
        _KB_ANALYSIS_HELPER = analysis_helper
    if ingestion_helper is not None:
        _KB_INGESTION_HELPER = ingestion_helper
    if chunk_text_for_ingestion is not None:
        _CHUNK_TEXT_FOR_INGESTION = chunk_text_for_ingestion


def get_kb_storage_helper() -> Any:
    if _KB_STORAGE_HELPER is None:
        msg = "KBStorageHelper is not registered; call set_kb_helpers during host bootstrap"
        raise RuntimeError(msg)
    return _KB_STORAGE_HELPER


def get_kb_analysis_helper() -> Any:
    if _KB_ANALYSIS_HELPER is None:
        msg = "KBAnalysisHelper is not registered; call set_kb_helpers during host bootstrap"
        raise RuntimeError(msg)
    return _KB_ANALYSIS_HELPER


def get_kb_ingestion_helper() -> Any:
    if _KB_INGESTION_HELPER is None:
        msg = "KBIngestionHelper is not registered; call set_kb_helpers during host bootstrap"
        raise RuntimeError(msg)
    return _KB_INGESTION_HELPER


def chunk_text_for_ingestion(*args: Any, **kwargs: Any) -> Any:
    if _CHUNK_TEXT_FOR_INGESTION is None:
        msg = "chunk_text_for_ingestion is not registered; call set_kb_helpers during host bootstrap"
        raise RuntimeError(msg)
    return _CHUNK_TEXT_FOR_INGESTION(*args, **kwargs)


# Module-level class proxies for ``KBStorageHelper.method`` style usage.
class _HelperProxy:
    def __init__(self, getter: Callable[[], Any]) -> None:
        self._getter = getter

    def __getattr__(self, item: str) -> Any:
        return getattr(self._getter(), item)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._getter()(*args, **kwargs)


KBStorageHelper = _HelperProxy(get_kb_storage_helper)
KBAnalysisHelper = _HelperProxy(get_kb_analysis_helper)
KBIngestionHelper = _HelperProxy(get_kb_ingestion_helper)
