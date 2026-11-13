"""One provider on every API Datacircle benchmarks: its rank and best plan on each."""

from __future__ import annotations

import re
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
    path_segment,
)


def provider_slug(value: Any) -> str:
    """Datacircle's slug of a provider name: lowercase letters and digits, the rest a hyphen (bright-data)."""
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def _api_row(provider: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    plans = [plan for plan in item.get("plans") or [] if isinstance(plan, dict)]
    scored = [plan for plan in plans if isinstance(plan.get("score"), (int, float))]
    best = max(scored, key=lambda plan: plan["score"]) if scored else (plans[0] if plans else {})
    return {
        "provider": provider.get("provider"),
        "api": item.get("api"),
        "slug": item.get("slug"),
        "rank": item.get("rank"),
        "plans": len(plans),
        "best_plan": best.get("plan"),
        "best_score": best.get("score"),
        "best_per_thousand": best.get("perThousand"),
        "best_page": item.get("bestPage"),
        "website": provider.get("website"),
    }


class DatacircleProviderComponent(Component):
    """Return one provider's rank on each API it sells, one row per API."""

    display_name = "Datacircle Provider"
    description = (
        "See how one provider, such as Hunter or Bright Data, ranks on every GTM API it sells, "
        "with its best plan on each. No API key needed."
    )
    documentation = DOCUMENTATION_URL
    icon = "Datacircle"
    name = "DatacircleProvider"

    inputs = [
        MessageTextInput(
            name="provider",
            display_name="Provider",
            info="The provider's name or slug, such as Hunter or bright-data.",
            required=True,
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
        Output(display_name="Table", name="dataframe", method="provider_dataframe"),
    ]

    def provider_apis(self) -> list[Data]:
        """Return one ``Data`` per API the provider sells."""
        slug = path_segment(provider_slug(self.provider))
        if not slug:
            error = "Enter a provider's name or slug, such as hunter."
            self.status = error
            return [Data(text=error, data={"error": error})]

        try:
            body = datacircle_get(f"/providers/{slug}", timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS))
            apis = body.get("apis") if isinstance(body, dict) else None
            if not isinstance(apis, list):
                msg = "Datacircle API returned a provider without an apis list."
                raise DatacircleAPIError(msg)
        except DatacircleAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        rows = [_api_row(body, item) for item in apis if isinstance(item, dict)]
        data = [Data(text=f"{row['provider']} on {row['api']}: rank {row['rank']}", data=row) for row in rows]
        self.status = data
        return data

    def provider_dataframe(self) -> DataFrame:
        return DataFrame(self.provider_apis())
