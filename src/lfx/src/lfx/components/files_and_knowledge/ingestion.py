"""Knowledge ingestion component — backward-compat shim.

The full implementation now lives in
:mod:`lfx.components.files_and_knowledge.knowledge` as the mode-driven
:class:`KnowledgeComponent`. ``KnowledgeIngestionComponent`` is kept as a
thin subclass so saved flows referencing the legacy node id
(``KnowledgeIngestion``) and the legacy module path keep loading and
running unchanged. New flows should use ``KnowledgeComponent`` directly.
"""

from __future__ import annotations

from typing import Any

from lfx.components.files_and_knowledge.knowledge import (
    MODE_INGEST,
    KnowledgeComponent,
    _inputs_for_mode,
)
from lfx.io import Output

# Preserved for callers that imported these constants from the legacy module.
astra_error_msg = "Knowledge ingestion is not supported in Astra cloud environment."


class KnowledgeIngestionComponent(KnowledgeComponent):
    """Create or append to Langflow Knowledge from a DataFrame.

    Pins the merged :class:`KnowledgeComponent` to ingest mode. All
    behavior is inherited unchanged.
    """

    display_name = "Knowledge Ingestion"
    description = "Create or update knowledge in Langflow."
    icon = "upload"
    name = "KnowledgeIngestion"
    # Hidden from the default palette — surfaces only when a saved flow
    # already references it. New flows should pick ``Knowledge`` instead.
    legacy = True
    replacement = ["files_and_knowledge.Knowledge"]

    # Pin the mode-default visibility at the class level so the canvas
    # renders the legacy "ingest-only" shape on first load.
    inputs = _inputs_for_mode(MODE_INGEST)
    outputs = [
        Output(
            display_name="Results",
            name="dataframe_output",
            method="build_kb_info",
            types=["JSON"],
            selected="JSON",
        ),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.mode = MODE_INGEST
