"""Search every plan Datacircle benchmarks, by API, provider or price."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, FloatInput, IntInput, MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.datacircle.datacircle_common import (
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    MAX_LIMIT,
    SORT_OPTIONS,
    DatacircleAPIError,
    clamp_limit,
    datacircle_get,
    plan_row,
)


class DatacircleSearchPlansComponent(Component):
    """Search the plans on Datacircle's sheet, one row per plan."""

    display_name = "Datacircle Search Plans"
    description = (
        "Search every plan of every GTM API Datacircle benchmarks, by provider or plan name, "
        "for one API or all, sorted by score or price. No API key needed."
    )
    documentation = DOCUMENTATION_URL
    icon = "Datacircle"
    name = "DatacircleSearchPlans"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Words that must all appear in the provider's or the plan's name, such as 'hunter'. "
            "Leave empty for every plan.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="api",
            display_name="API",
            info="Only plans of this API, its slug or its name, such as email-finder. Leave empty for every API.",
            tool_mode=True,
        ),
        DropdownInput(
            name="sort",
            display_name="Sort By",
            info="score: the best first. price: the lowest price per 1,000 first. provider: A to Z.",
            options=SORT_OPTIONS,
            value="score",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Max Plans",
            info=f"How many plans to return, from 1 to {MAX_LIMIT}.",
            value=10,
            advanced=True,
        ),
        IntInput(
            name="offset",
            display_name="Offset",
            info="How many found plans to skip first, to page through the results.",
            value=0,
            advanced=True,
        ),
        BoolInput(
            name="all_fields",
            display_name="All Fields",
            info="Return every field of each plan (rate limits, speed, fields returned...) instead of the main ones.",
            value=False,
            advanced=True,
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
        Output(display_name="Table", name="dataframe", method="search_plans_dataframe"),
    ]

    def search_plans(self) -> list[Data]:
        """Return one ``Data`` per plan found."""
        params: dict[str, object] = {
            "sort": self.sort if self.sort in SORT_OPTIONS else "score",
            "limit": clamp_limit(self.limit, default=10),
            "offset": max(int(self.offset or 0), 0),
        }
        for field in ("query", "api"):
            value = str(getattr(self, field, None) or "").strip()
            if value:
                params[field] = value

        try:
            body = datacircle_get("/plans", timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS), params=params)
            plans = body.get("plans") if isinstance(body, dict) else None
            if not isinstance(plans, list):
                msg = "Datacircle API returned an answer without a plans list."
                raise DatacircleAPIError(msg)
        except DatacircleAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [
            Data(
                text=f"{plan.get('provider')} {plan.get('plan')} ({plan.get('api')}): score {plan.get('score')}",
                data=plan_row(plan, all_fields=bool(self.all_fields)),
            )
            for plan in plans
            if isinstance(plan, dict)
        ]
        self.status = data
        return data

    def search_plans_dataframe(self) -> DataFrame:
        return DataFrame(self.search_plans())
