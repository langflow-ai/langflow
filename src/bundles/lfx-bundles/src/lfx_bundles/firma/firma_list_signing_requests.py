"""List Firma signing requests, newest first."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.firma.firma_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    REQUEST_STATUSES,
    FirmaAPIError,
    list_page,
    text_value,
)

ALL_STATUSES = "all"


class FirmaListSigningRequestsComponent(Component):
    """List one page of signing requests, with optional filters."""

    display_name = "Firma List Signing Requests"
    description = "List Firma signing requests, newest first, filtered by status, name or signer email."
    documentation = DOCUMENTATION_URL
    icon = "Firma"
    name = "FirmaListSigningRequests"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Firma API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        DropdownInput(
            name="status_filter",
            display_name="Status",
            info="Only list requests with this status.",
            options=[ALL_STATUSES, *REQUEST_STATUSES],
            value=ALL_STATUSES,
            tool_mode=True,
        ),
        MessageTextInput(
            name="name_filter",
            display_name="Name Contains",
            info="Only list requests whose name contains this text.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="signer_email",
            display_name="Signer Email",
            info="Only list requests sent to this email address.",
            tool_mode=True,
        ),
        IntInput(
            name="page",
            display_name="Page",
            info="The page of results, starting at 1.",
            value=1,
            advanced=True,
        ),
        IntInput(
            name="page_size",
            display_name="Page Size",
            info="Requests per page, from 1 to 200.",
            value=25,
            advanced=True,
        ),
        BoolInput(
            name="exclude_deleted",
            display_name="Exclude Deleted",
            info="Leave deleted requests out of the list.",
            value=True,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Firma to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="list_dataframe"),
    ]

    def list_requests(self) -> list[Data]:
        """Return one ``Data`` per signing request, with the request name as ``text``."""
        try:
            status = text_value(self.status_filter).lower() or ALL_STATUSES
            if status != ALL_STATUSES and status not in REQUEST_STATUSES:
                msg = f"Choose a status from: {ALL_STATUSES}, {', '.join(REQUEST_STATUSES)}; got {status!r}."
                raise FirmaAPIError(msg)
            filters: dict[str, Any] = {}
            if status != ALL_STATUSES:
                filters["status"] = status
            for param, value in (("name", self.name_filter), ("signer_email", self.signer_email)):
                if text_value(value):
                    filters[param] = text_value(value)
            # Deleted requests cannot be opened by the other components, so they
            # are left out unless asked for.
            if status != "deleted" and self.exclude_deleted:
                filters["exclude_deleted"] = "true"
            data = list_page(self, "/signing-requests", filters)
        except FirmaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]
        self.status = data
        return data

    def list_dataframe(self) -> DataFrame:
        return DataFrame(self.list_requests())
