"""Lazy component re-exports for the ``notion`` bundle.

Mirrors the pre-extraction layout of ``lfx.components.notion`` so saved
flows that referenced the module-level class
(e.g. ``lfx.components.notion.<Class>``) keep resolving via the
migration table after rewrite to
``lfx_notion.components.notion.<Class>``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .add_content_to_page import AddContentToPage
    from .create_page import NotionPageCreator
    from .list_database_properties import NotionDatabaseProperties
    from .list_pages import NotionListPages
    from .list_users import NotionUserList
    from .page_content_viewer import NotionPageContent
    from .search import NotionSearch
    from .update_page_property import NotionPageUpdate

_dynamic_imports = {
    "AddContentToPage": "add_content_to_page",
    "NotionDatabaseProperties": "list_database_properties",
    "NotionListPages": "list_pages",
    "NotionPageContent": "page_content_viewer",
    "NotionPageCreator": "create_page",
    "NotionPageUpdate": "update_page_property",
    "NotionSearch": "search",
    "NotionUserList": "list_users",
}

__all__ = [
    "AddContentToPage",
    "NotionDatabaseProperties",
    "NotionListPages",
    "NotionPageContent",
    "NotionPageCreator",
    "NotionPageUpdate",
    "NotionSearch",
    "NotionUserList",
]


def __getattr__(attr_name: str) -> Any:
    if attr_name not in _dynamic_imports:
        msg = f"module {__name__!r} has no attribute {attr_name!r}"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import {attr_name!r} from {__name__!r}: {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
