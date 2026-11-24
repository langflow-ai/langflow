"""Retirement metadata shared by compatibility classes and offline upgrade reports.

These components are no longer in the core palette. Keep their retirement guidance available
without importing component implementations or installing their optional bundles.
"""

from functools import lru_cache
from typing import Any

from lfx.utils.component_aliases import flatten_components_with_aliases

CHROMA_RETIRED_IN = "1.13.0"
CHROMA_REPLACEMENT = ("files_and_knowledge.Knowledge",)
ALTK_RETIRED_IN = "1.13.0"
ALTK_REPLACEMENT = ("models_and_agents.Agent",)


def retired_component_metadata() -> dict[str, dict[str, dict[str, Any]]]:
    """Return reporting metadata, not runnable registry templates, for retired bundle components."""
    components = (
        ("chroma", "ChromaVectorStoreComponent", "Chroma", CHROMA_RETIRED_IN, CHROMA_REPLACEMENT),
        ("chroma", "LocalDBComponent", "LocalDB", CHROMA_RETIRED_IN, CHROMA_REPLACEMENT),
        ("altk", "ALTKAgentComponent", "ALTK Agent", ALTK_RETIRED_IN, ALTK_REPLACEMENT),
    )
    components += tuple(
        ("mrscraper", name, name, "1.13.0", ("mrscraper.MrscraperFetchHtml",))
        for name in (
            "MrscraperAiScraper",
            "MrscraperBatchScrape",
            "MrscraperCrawlWebsite",
            "MrscraperGetResult",
            "MrscraperGetResults",
            "MrscraperRunAiScraper",
            "MrscraperRunManualScraper",
        )
    )
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for bundle, class_name, name, retired_in, replacement in components:
        result.setdefault(bundle, {})[f"ext:{bundle}:{class_name}@official"] = {
            "name": name,
            "bundle": bundle,
            "retired_in": retired_in,
            "replacement": list(replacement),
        }
    return result


@lru_cache(maxsize=1)
def retirement_lookup() -> dict[str, dict]:
    """Guidance for saved node types whose bundle is absent, including legacy names."""
    from lfx.extension.migration.loader import load_migration_table

    lookup = dict(flatten_components_with_aliases(retired_component_metadata()))
    table, _ = load_migration_table()
    if table is not None:
        for entry in table.entries:
            if entry.target in lookup:
                lookup.setdefault(entry.legacy_value, lookup[entry.target])
    return lookup


def replacement_label(reference: str) -> str:
    """Use palette labels for known replacements and retain unknown references."""
    return {
        "files_and_knowledge.Knowledge": "Knowledge",
        "models_and_agents.Agent": "Agent",
        "mrscraper.MrscraperFetchHtml": "MrScraper Scrape HTML",
    }.get(reference, reference)
