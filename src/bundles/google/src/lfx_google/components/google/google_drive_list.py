"""Drive: List Files (app files) — wave-1 action (INT-10, google.drive.list).

Wave 1 ships on ``drive.file`` only, which is non-sensitive and therefore needs
no Google security assessment. The trade is reach: ``files.list`` under
``drive.file`` returns only files this app created or the user explicitly opened
with it, so an otherwise-correct configuration can legitimately list nothing.
That limit is in the display name and the docs on purpose.
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from ._workspace_client import workspace_action
from ._workspace_inputs import DRIVE_FILE_SCOPE, google_connection_input

CAPABILITY = "google.drive.list"

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
DEFAULT_FIELDS = "nextPageToken, incompleteSearch, files(id, name, mimeType, modifiedTime, size, webViewLink)"


class GoogleDriveListComponent(Component):
    """List Drive files visible to the app under the ``drive.file`` scope."""

    display_name = "Drive: List Files (app files)"
    description = (
        "Lists Google Drive files this app created or the user opened with it. "
        "The drive.file scope cannot see the rest of the user's Drive."
    )
    documentation: str = "https://docs.langflow.org/bundles-google"
    icon = "GoogleDrive"
    name = "GoogleDriveListComponent"

    inputs = [
        google_connection_input(required_scopes=[DRIVE_FILE_SCOPE], capabilities=[CAPABILITY]),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Drive query (q) syntax, for example \"name contains 'report'\".",
        ),
        IntInput(
            name="page_size",
            display_name="Page Size",
            info=f"Files per page, maximum {MAX_PAGE_SIZE}.",
            value=DEFAULT_PAGE_SIZE,
            advanced=True,
        ),
        MessageTextInput(
            name="page_token",
            display_name="Page Token",
            info="Continue a previous listing.",
            advanced=True,
        ),
        MessageTextInput(
            name="order_by",
            display_name="Order By",
            info="Drive orderBy expression, for example 'modifiedTime desc'.",
            advanced=True,
        ),
        BoolInput(
            name="include_shared_drives",
            display_name="Include Shared Drives",
            info="Sets includeItemsFromAllDrives and supportsAllDrives.",
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="fields",
            display_name="Fields",
            info="Partial-response selector. Leave empty for the default field set.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Files", name="files", method="list_files"),
        Output(display_name="Listing", name="listing", method="list_page"),
    ]

    def _request_params(self) -> dict[str, object]:
        page_size = int(self.page_size) if self.page_size else DEFAULT_PAGE_SIZE
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            msg = f"page_size must be between 1 and {MAX_PAGE_SIZE}, got {page_size}"
            raise ValueError(msg)
        params: dict[str, object] = {
            "pageSize": page_size,
            "fields": (self.fields or "").strip() or DEFAULT_FIELDS,
        }
        if self.query:
            params["q"] = self.query
        if self.page_token:
            params["pageToken"] = self.page_token
        if self.order_by:
            params["orderBy"] = self.order_by
        if self.include_shared_drives:
            params["includeItemsFromAllDrives"] = True
            params["supportsAllDrives"] = True
        return params

    async def _list(self) -> dict:
        # Both outputs describe the same page, so a flow wiring each of them must
        # not spend two Drive calls (and two quota units) to get them.
        cached = getattr(self, "_listing_response", None)
        if cached is not None:
            return cached
        params = self._request_params()
        async with workspace_action(self, capability=CAPABILITY, api="drive", version="v3") as service:
            response = await service.execute(lambda client: client.files().list(**params))
        self._listing_response = response
        return response

    async def list_page(self) -> Data:
        """Return the whole ``files.list`` page: files plus paging metadata."""
        response = await self._list()
        data = Data(
            data={
                "files": list(response.get("files", [])),
                "next_page_token": response.get("nextPageToken"),
                "incomplete_search": bool(response.get("incompleteSearch", False)),
            }
        )
        self.status = data
        return data

    async def list_files(self) -> DataFrame:
        """Return one row per file resource."""
        response = await self._list()
        rows = [Data(data=dict(entry)) for entry in response.get("files", [])]
        frame = DataFrame(rows)
        self.status = frame
        return frame
