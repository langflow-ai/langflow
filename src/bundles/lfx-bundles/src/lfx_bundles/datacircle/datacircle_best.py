"""Who is best for one API, from Datacircle's benchmark."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, FloatInput, IntInput, MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.datacircle.datacircle_common import (
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    MAX_LIMIT,
    DatacircleAPIError,
    clamp_limit,
    datacircle_get,
    path_segment,
    plan_row,
)


class DatacircleBestComponent(Component):
    """Return an API's plans, the best score first, one row per plan."""

    display_name = "Datacircle Best Plans"
    description = (
        "See who is best for one GTM API, such as email-finder: its plans ranked by Datacircle's benchmark, "
        "the best first, with their price per 1,000. No API key needed."
    )
    documentation = DOCUMENTATION_URL
    icon = "Datacircle"
    name = "DatacircleBest"

    inputs = [
        MessageTextInput(
            name="api",
            display_name="API",
            info="The API's slug, such as email-finder or linkedin-profile. Datacircle List APIs gives every slug.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Max Plans",
            info=f"How many plans to return, from 1 to {MAX_LIMIT}.",
            value=5,
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
        Output(display_name="Table", name="dataframe", method="best_dataframe"),
    ]

    def best(self) -> list[Data]:
        """Return one ``Data`` per plan, the best first."""
        slug = path_segment(self.api)
        if not slug:
            error = "Enter an API slug, such as email-finder."
            self.status = error
            return [Data(text=error, data={"error": error})]

        try:
            body = datacircle_get(
                f"/apis/{slug}/best",
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                params={"limit": clamp_limit(self.limit, default=5)},
            )
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
                text=f"{plan.get('provider')} {plan.get('plan')}: score {plan.get('score')}",
                data=plan_row(plan, all_fields=bool(self.all_fields)),
            )
            for plan in plans
            if isinstance(plan, dict)
        ]
        self.status = data
        return data

    def best_dataframe(self) -> DataFrame:
        return DataFrame(self.best())
