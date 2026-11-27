"""List Firma templates, newest first."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.firma.firma_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    FirmaAPIError,
    list_page,
    text_value,
)


class FirmaListTemplatesComponent(Component):
    """List one page of templates, optionally filtered by name."""

    display_name = "Firma List Templates"
    description = "List the Firma templates in the workspace, newest first, with their IDs and names."
    documentation = DOCUMENTATION_URL
    icon = "Firma"
    name = "FirmaListTemplates"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Firma API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="name_filter",
            display_name="Name Contains",
            info="Only list templates whose name contains this text.",
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
            info="Templates per page, from 1 to 200.",
            value=25,
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

    def list_templates(self) -> list[Data]:
        """Return one ``Data`` per template, with the template name as ``text``."""
        try:
            filters = {"name": text_value(self.name_filter)} if text_value(self.name_filter) else {}
            data = list_page(self, "/templates", filters)
        except FirmaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]
        self.status = data
        return data

    def list_dataframe(self) -> DataFrame:
        return DataFrame(self.list_templates())
