from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from .olostep_answer import OlostepAnswerComponent
    from .olostep_crawl import OlostepCrawlComponent
    from .olostep_map import OlostepMapComponent
    from .olostep_scrape import OlostepScrapeComponent
    from .olostep_search import OlostepSearchComponent

_dynamic_imports = {
    "OlostepAnswerComponent": "olostep_answer",
    "OlostepCrawlComponent": "olostep_crawl",
    "OlostepMapComponent": "olostep_map",
    "OlostepScrapeComponent": "olostep_scrape",
    "OlostepSearchComponent": "olostep_search",
}

__all__ = [
    "OlostepAnswerComponent",
    "OlostepCrawlComponent",
    "OlostepMapComponent",
    "OlostepScrapeComponent",
    "OlostepSearchComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import Olostep components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    """List the lazily imported component names."""
    return list(__all__)
