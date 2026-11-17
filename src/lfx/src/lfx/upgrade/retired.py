"""Retirement metadata shared by compatibility classes and offline upgrade reports.

These components are no longer in the core palette. Keep their retirement guidance available
without importing component implementations or installing their optional bundles.
"""

from typing import Any

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
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for bundle, class_name, name, retired_in, replacement in components:
        result.setdefault(bundle, {})[f"ext:{bundle}:{class_name}@official"] = {
            "name": name,
            "bundle": bundle,
            "retired_in": retired_in,
            "replacement": list(replacement),
        }
    return result
