"""Declarations for authenticated latest-state page polling."""

from lfx.io import MessageTextInput

from lfx_confluence.base import ConfluencePageTriggerComponent
from lfx_confluence.manifest import connection_input


class ConfluenceOnPageCreatedTriggerComponent(ConfluencePageTriggerComponent):
    display_name = "Confluence On Page Created"
    description = (
        "Observe newly created pages after an initial approved-space baseline. "
        "Moved old pages do not count as creation."
    )
    name = "ConfluenceOnPageCreatedTrigger"
    trigger_kind = "confluence.page_created"
    inputs = [
        connection_input("confluence.trigger.created", required=False),
        MessageTextInput(
            name="space_id",
            display_name="Space ID",
            required=True,
            info="An approved numeric space ID with at most 5000 observed pages.",
        ),
    ]


class ConfluenceOnPageUpdatedTriggerComponent(ConfluencePageTriggerComponent):
    display_name = "Confluence On Page Updated"
    description = "Observe version changes of previously seen published pages. Intermediate edits can be missed."
    name = "ConfluenceOnPageUpdatedTrigger"
    trigger_kind = "confluence.page_updated"
    inputs = [
        connection_input("confluence.trigger.updated", required=False),
        MessageTextInput(
            name="space_id",
            display_name="Space ID",
            required=True,
            info="An approved numeric space ID with at most 5000 observed pages.",
        ),
    ]
