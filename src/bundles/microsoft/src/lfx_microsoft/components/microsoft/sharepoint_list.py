"""List driveItem children in OneDrive or a SharePoint document library."""

from __future__ import annotations

from lfx_microsoft.base import (
    Data,
    IntInput,
    Message,
    MessageTextInput,
    MicrosoftGraphComponent,
    Output,
    as_list,
)
from lfx_microsoft.graph import drive_children_path, drive_root, odata_params
from lfx_microsoft.manifest import connection_input

DEFAULT_TOP = 100


class SharePointListComponent(MicrosoftGraphComponent):
    """List the children of a OneDrive or SharePoint folder."""

    display_name = "SharePoint/OneDrive: List Items"
    description = "List files and folders the connected user can read."
    documentation = "https://learn.microsoft.com/en-us/graph/api/driveitem-list-children"
    name = "SharePointListItems"
    capability_id = "microsoft.files.list"

    inputs = [
        connection_input(capability_id),
        MessageTextInput(
            name="drive_id",
            display_name="Drive ID",
            info="Another user's or a shared drive. Requires Files.Read.All. Defaults to the user's OneDrive.",
        ),
        MessageTextInput(
            name="site_id",
            display_name="Site ID",
            info="A SharePoint site's default document library. Requires Sites.Read.All.",
        ),
        MessageTextInput(
            name="item_id",
            display_name="Folder Item ID",
            info="Defaults to the drive root.",
            advanced=True,
        ),
        MessageTextInput(
            name="path",
            display_name="Folder Path",
            info="Folder path relative to the drive root, used when no item id is given.",
            advanced=True,
        ),
        IntInput(name="top", display_name="Max Results", value=DEFAULT_TOP),
        MessageTextInput(name="select", display_name="Select Fields", is_list=True, advanced=True),
        MessageTextInput(
            name="order_by",
            display_name="Order By",
            info="OData $orderby expression, for example name asc.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Items", name="items", method="list_items"),
        Output(display_name="Next Link", name="next_link", method="next_page_link"),
    ]

    _next_link: str | None = None

    def _scope_inputs(self) -> dict[str, str]:
        """Inputs the conditional-scope pre-flight predicates read."""
        scope: dict[str, str] = {}
        if drive_id := (self.drive_id or "").strip():
            scope["drive_id"] = drive_id
        if site_id := (self.site_id or "").strip():
            scope["site_id"] = site_id
        return scope

    async def list_items(self) -> list[Data]:
        """Return the folder's children as Data rows."""
        scope = self._scope_inputs()
        root = drive_root(scope.get("drive_id", ""), scope.get("site_id", ""))
        target = drive_children_path(root, (self.item_id or "").strip(), (self.path or "").strip())
        params = odata_params(
            top=self.top or DEFAULT_TOP,
            select=as_list(self.select) or None,
            order_by=(self.order_by or "").strip() or None,
        )
        lease = self.lease()
        async with self.action(lease, scope) as client:
            items, next_link = await client.paginate(
                target,
                params=params,
                limit=self.top or DEFAULT_TOP,
            )
        self._next_link = next_link
        rows = [Data(data=item) for item in items]
        self.status = f"{len(rows)} item(s)"
        return rows

    async def next_page_link(self) -> Message:
        """Return the unfollowed ``@odata.nextLink``, if Graph supplied one."""
        if self._next_link is None:
            await self.list_items()
        return Message(text=self._next_link or "")
