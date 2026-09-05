"""Search the signed-in user's mail (GET /me/messages)."""

from __future__ import annotations

from lfx_microsoft.base import (
    BoolInput,
    Data,
    IntInput,
    Message,
    MessageTextInput,
    MicrosoftGraphComponent,
    Output,
    as_list,
)
from lfx_microsoft.graph import odata_params, prefer_header
from lfx_microsoft.manifest import connection_input

DEFAULT_TOP = 10


class OutlookSearchComponent(MicrosoftGraphComponent):
    """List or search Outlook messages through delegated Graph permissions."""

    display_name = "Outlook: Search Mail"
    description = "Search the connected user's Outlook mailbox."
    documentation = "https://learn.microsoft.com/en-us/graph/api/user-list-messages"
    name = "OutlookSearchMail"
    capability_id = "microsoft.outlook.search"

    inputs = [
        connection_input(capability_id),
        MessageTextInput(
            name="search",
            display_name="Search",
            info="Free-text $search expression. Graph rejects $search combined with $filter.",
        ),
        MessageTextInput(
            name="filter",
            display_name="Filter",
            info="OData $filter expression, for example isRead eq false.",
        ),
        MessageTextInput(
            name="folder_id",
            display_name="Mail Folder ID",
            info="Restrict the search to one mailFolders/{id}. Defaults to the whole mailbox.",
            advanced=True,
        ),
        IntInput(
            name="top",
            display_name="Max Results",
            info="1 to 1000. Graph defaults to 10.",
            value=DEFAULT_TOP,
        ),
        MessageTextInput(
            name="select",
            display_name="Select Fields",
            info="Message properties to return.",
            is_list=True,
            advanced=True,
        ),
        BoolInput(
            name="include_body",
            display_name="Include Body",
            info="Return message bodies as plain text. Requires Mail.Read.",
            value=False,
        ),
    ]

    outputs = [
        Output(display_name="Messages", name="messages", method="search_messages"),
        Output(display_name="Next Link", name="next_link", method="next_page_link"),
    ]

    _next_link: str | None = None
    # Both outputs come from a single Graph listing. The rows are cached on
    # the instance so that evaluating "Next Link" first -- or evaluating both
    # outputs -- costs one request, not two.
    _rows: list[Data] | None = None

    def _path(self) -> str:
        folder = (self.folder_id or "").strip()
        if folder:
            return f"/me/mailFolders/{folder}/messages"
        return "/me/messages"

    async def search_messages(self) -> list[Data]:
        """Return the matching messages as Data rows."""
        if self._rows is not None:
            self.status = f"{len(self._rows)} message(s)"
            return self._rows
        search = (self.search or "").strip()
        filter_expression = (self.filter or "").strip()
        params = odata_params(
            top=self.top or DEFAULT_TOP,
            select=as_list(self.select) or None,
            filter_expression=filter_expression or None,
            search=search or None,
        )
        headers = prefer_header(None, body_as_text=bool(self.include_body))
        lease = self.lease()
        async with self.action(lease) as client:
            items, next_link = await client.paginate(
                self._path(),
                params=params,
                headers=headers or None,
                limit=self.top or DEFAULT_TOP,
            )
        self._next_link = next_link
        rows = [Data(data=item) for item in items]
        self._rows = rows
        self.status = f"{len(rows)} message(s)"
        return rows

    async def next_page_link(self) -> Message:
        """Return the unfollowed ``@odata.nextLink``, if Graph supplied one."""
        if self._rows is None:
            await self.search_messages()
        return Message(text=self._next_link or "")
