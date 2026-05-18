"""Knowledge Base retrieval component — backward-compat shim.

The full implementation now lives in
:mod:`lfx.components.files_and_knowledge.knowledge` as the mode-driven
:class:`KnowledgeComponent`. ``KnowledgeBaseComponent`` remains as a thin
subclass so saved flows referencing the legacy node id (``KnowledgeBase``)
and the legacy module path keep loading and running unchanged.

The module-level ``_parse_metadata_filter`` / ``_chunk_matches_filter``
helpers are re-exported here because existing unit tests import them
from this module path — see
``src/backend/tests/unit/components/files_and_knowledge/test_retrieval.py``.
"""

from __future__ import annotations

from typing import Any

from lfx.components.files_and_knowledge.knowledge import (
    MODE_RETRIEVE,
    KnowledgeComponent,
    _chunk_matches_filter,
    _inputs_for_mode,
    _parse_metadata_filter,
)
from lfx.io import Output

__all__ = [
    "KnowledgeBaseComponent",
    "_chunk_matches_filter",
    "_parse_metadata_filter",
]

astra_error_msg = "Knowledge retrieval is not supported in Astra cloud environment."


class KnowledgeBaseComponent(KnowledgeComponent):
    """Search and retrieve data from knowledge.

    Pins the merged :class:`KnowledgeComponent` to retrieve mode. All
    behavior is inherited unchanged.
    """

    display_name = "Knowledge Base"
    description = "Search and retrieve data from knowledge."
    icon = "download"
    name = "KnowledgeBase"
    # Hidden from the default palette — surfaces only when a saved flow
    # already references it. New flows should pick ``Knowledge`` instead.
    legacy = True
    replacement = ["files_and_knowledge.Knowledge"]

    # Pin the mode-default visibility at the class level so the canvas
    # renders the legacy "retrieve-only" shape on first load.
    inputs = _inputs_for_mode(MODE_RETRIEVE)
    outputs = [
        Output(
            display_name="Results",
            name="retrieve_data",
            method="retrieve_data",
            info="Returns the data from the selected knowledge base.",
            types=["Table"],
            selected="Table",
        ),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.mode = MODE_RETRIEVE
