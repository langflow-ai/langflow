from __future__ import annotations

import json

from cleanedweb.exceptions import CleanedWebError
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, IntInput, MessageTextInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from lfx_bundles.cleanedweb.cleanedweb_common import error_message, error_rows, make_client

DEFAULT_LIMIT = 5
MAX_LIMIT = 20


def _endpoint_inputs(input_schema: dict) -> dict:
    """``{name: "type, required - description"}`` for an endpoint's input schema."""
    properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
    if not isinstance(properties, dict):
        return {}
    required = set(input_schema.get("required") or [])
    described = {}
    for name, raw_spec in properties.items():
        spec = raw_spec if isinstance(raw_spec, dict) else {}
        parts = [str(spec.get("type", "any"))]
        if name in required:
            parts.append("required")
        text = ", ".join(parts)
        if spec.get("description"):
            text += f" - {spec['description']}"
        described[name] = text
    return described


class CleanedWebFindAPIComponent(Component):
    """Search the CleanedWeb catalog of maintained web data APIs."""

    display_name = "CleanedWeb Find API"
    description = (
        "Find a maintained API for a public website in the CleanedWeb catalog. "
        "Returns each API's id, endpoints and the inputs to run it with. No API key needed."
    )
    documentation = "https://cleanedweb.com/docs/"
    icon = "Globe"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Query",
            info="What to look for, for example 'steam reviews' or 'remote python jobs'.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="site",
            display_name="Site",
            info="Only APIs for this site: a domain, URL or name, for example 'github.com'.",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Max Results",
            value=DEFAULT_LIMIT,
            advanced=True,
            range_spec=RangeSpec(min=1, max=MAX_LIMIT, step=1, step_type="int"),
            info="Maximum number of APIs to return (1-20).",
        ),
        BoolInput(
            name="include_inputs",
            display_name="Include Endpoint Inputs",
            value=True,
            advanced=True,
            info="Read each API's contract to list the inputs of every endpoint.",
        ),
    ]

    outputs = [
        # The method name is the tool name in tool mode; keep it provider specific.
        Output(display_name="Table", name="dataframe", method="cleanedweb_find_api"),
    ]

    def _limit(self) -> int:
        requested = DEFAULT_LIMIT if self.limit is None else int(self.limit)
        return max(1, min(requested, MAX_LIMIT))

    def _api_row(self, client, api) -> Data:
        endpoints = [
            {"endpoint_id": e.endpoint_id, "name": e.name, "description": e.description} for e in api.endpoints
        ]
        if self.include_inputs:
            try:
                contract = client.catalog.get(api.slug or api.api_id)
            except CleanedWebError:
                contract = None
            if contract is not None:
                by_id = {e.endpoint_id: e for e in contract.endpoints}
                for endpoint in endpoints:
                    found = by_id.get(endpoint["endpoint_id"])
                    if found is not None:
                        endpoint["inputs"] = _endpoint_inputs(found.input_schema)
        data = {
            "api_id": api.api_id,
            "slug": api.slug or "",
            "name": api.name,
            "site": api.site_domain or api.site_name,
            "category": api.category,
            "description": api.description,
            "key_fields": ", ".join(api.key_fields),
            "endpoints": json.dumps(endpoints, ensure_ascii=False),
        }
        return Data(text=f"{api.name} ({data['site']}): {api.description}", data=data)

    def fetch_content(self) -> list[Data]:
        query = (self.query or "").strip()
        site = (self.site or "").strip()
        if not query and not site:
            return error_rows("Set a Query or a Site to search the CleanedWeb catalog.")
        try:
            with make_client() as client:
                apis = client.catalog.find(q=query or None, site=site or None, limit=self._limit())
                rows = [self._api_row(client, api) for api in apis]
        except Exception as e:  # noqa: BLE001 - surfaced as an error row, never raised into the flow
            return error_rows(error_message(e))
        self.status = rows
        return rows

    def cleanedweb_find_api(self) -> DataFrame:
        """Search the catalog and return the matching APIs as a DataFrame."""
        return DataFrame(self.fetch_content())
