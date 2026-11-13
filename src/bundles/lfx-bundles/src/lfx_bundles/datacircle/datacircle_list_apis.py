"""List every API Datacircle benchmarks, with the best plan of each."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.datacircle.datacircle_common import (
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    DatacircleAPIError,
    datacircle_get,
)


def _api_row(item: dict[str, Any]) -> dict[str, Any]:
    best = item.get("best") if isinstance(item.get("best"), dict) else {}
    return {
        "api": item.get("api"),
        "slug": item.get("slug"),
        "plans": item.get("plans"),
        "providers": item.get("providers"),
        "best_provider": best.get("provider"),
        "best_plan": best.get("plan"),
        "best_score": best.get("score"),
        "best_per_thousand": best.get("perThousand"),
        "sheet_page": item.get("sheetPage"),
        "best_page": item.get("bestPage"),
    }


class DatacircleListAPIsComponent(Component):
    """List the APIs on Datacircle's sheet, one row per API with its slug and best plan."""

    display_name = "Datacircle List APIs"
    description = (
        "List every GTM API Datacircle benchmarks (email finders, enrichment, scraping...), "
        "with its slug and its best plan. No API key needed."
    )
    documentation = DOCUMENTATION_URL
    icon = "Datacircle"
    name = "DatacircleListAPIs"

    inputs = [
        MessageTextInput(
            name="search",
            display_name="Search",
            info="Only list the APIs whose name or slug has all these words, such as 'email'. Leave empty for every API.",
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Datacircle to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="list_apis_dataframe"),
    ]

    def list_apis(self) -> list[Data]:
        """Return one ``Data`` per API."""
        try:
            body = datacircle_get("/apis", timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS))
            if not isinstance(body, list):
                msg = "Datacircle API returned an unexpected response shape for /apis."
                raise DatacircleAPIError(msg)
        except DatacircleAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        words = str(self.search or "").lower().split()
        rows = [_api_row(item) for item in body if isinstance(item, dict)]
        if words:
            rows = [row for row in rows if all(word in f"{row['api']} {row['slug']}".lower() for word in words)]
        data = [Data(text=f"{row['api']} ({row['slug']})", data=row) for row in rows]
        self.status = data
        return data

    def list_apis_dataframe(self) -> DataFrame:
        return DataFrame(self.list_apis())
