"""Read rows from a Jsonify dataset.

Jsonify pipelines run on a schedule, repair themselves when a source changes,
and publish the result as a dataset. Each dataset has a serve URL that returns
its latest rows as JSON with paging, column selection, exact-match filters and
version pinning. The URL is the credential, so it is handled as a secret and
never exposed to the agent.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from langchain_core.tools import StructuredTool
from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.io import IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.utils.ssrf_httpx import ssrf_safe_httpx_get
from lfx.utils.ssrf_protection import SSRFProtectionError
from pydantic import BaseModel, Field

PAGE_SIZE = 1000
SYSTEM_COLUMNS = ("_parent_row_id", "_source_key")


class JsonifyDatasetComponent(Component):
    display_name = "Jsonify Dataset"
    description = (
        "Read rows from a Jsonify dataset. Jsonify pipelines run on a schedule and repair themselves "
        "when a source changes, so the flow reads maintained data instead of scraping. "
        "Use as a step in a flow or as a tool for an agent."
    )
    documentation: str = "https://docs.langflow.org/bundles-jsonify"
    icon = "Database"
    name = "JsonifyDataset"

    inputs = [
        SecretStrInput(
            name="serve_url",
            display_name="Dataset Serve URL",
            info=(
                "The serve URL of a Jsonify dataset, from the dataset's Integrations > REST API tab. "
                "It looks like https://factory.jsonify.com/api/serve/<id>. Treat it as a secret."
            ),
            required=True,
            password=True,
        ),
        StrInput(
            name="columns",
            display_name="Columns",
            info="Comma-separated column names to return, for example '_row_id, competitor, url'. Empty returns all.",
        ),
        MultilineInput(
            name="filters",
            display_name="Filters",
            info=(
                "JSON object of exact, case-sensitive column matches combined with AND, "
                'for example {"competitor": "Klue"}. Up to 10 filters.'
            ),
            value="",
        ),
        IntInput(
            name="max_rows",
            display_name="Max rows",
            info="Maximum number of rows to return. 0 returns all matching rows.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="version",
            display_name="Version",
            info="Dataset version to read. 0 reads the active version.",
            value=0,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="DataFrame", name="dataframe", type_=DataFrame, method="fetch_dataframe"),
        Output(display_name="Rows", name="rows", type_=list[Data], method="fetch_rows"),
        Output(display_name="Tool", name="tool", type_=Tool, method="build_tool"),
    ]

    class ToolSchema(BaseModel):
        """Parameters the agent may pass. The serve URL stays in the component."""

        filters: dict[str, str] = Field(
            default_factory=dict,
            description="Exact, case-sensitive column matches combined with AND, for example {'competitor': 'Klue'}.",
        )
        columns: list[str] = Field(default_factory=list, description="Column names to return. Empty returns all.")
        max_rows: int = Field(100, description="Maximum number of rows to return.")

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------

    def fetch_rows(self) -> list[Data]:
        result = self._fetch(
            columns=self._parse_columns(self.columns),
            filters=self._parse_filters(self.filters),
            max_rows=self.max_rows or None,
            version=self.version or None,
        )
        data = [Data(data=row) for row in result["rows"]]
        self.status = data
        return data

    def fetch_dataframe(self) -> DataFrame:
        result = self._fetch(
            columns=self._parse_columns(self.columns),
            filters=self._parse_filters(self.filters),
            max_rows=self.max_rows or None,
            version=self.version or None,
        )
        frame = DataFrame(result["rows"])
        self.status = frame
        return frame

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="read_jsonify_dataset",
            description=(
                "Read rows from a maintained Jsonify dataset. Rows are current without scraping. "
                "Pass filters to match column values exactly and columns to limit the fields returned."
            ),
            func=self._run_for_tool,
            args_schema=self.ToolSchema,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_for_tool(
        self, filters: dict[str, str] | None = None, columns: list[str] | None = None, max_rows: int = 100
    ) -> str:
        try:
            result = self._fetch(
                columns=columns or None,
                filters=filters or None,
                max_rows=max_rows or None,
                version=self.version or None,
            )
        except (SSRFProtectionError, httpx.HTTPError, ValueError) as e:
            return f"Error reading Jsonify dataset: {e}"
        return json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _parse_columns(value: str | None) -> list[str] | None:
        if not value:
            return None
        columns = [c.strip() for c in value.split(",") if c.strip()]
        return columns or None

    @staticmethod
    def _parse_filters(value: str | None) -> dict[str, str] | None:
        if not value or not value.strip():
            return None
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            msg = "Filters must be a JSON object of column name to value."
            raise TypeError(msg)
        return {str(k): str(v) for k, v in parsed.items()}

    @staticmethod
    def _build_params(
        *,
        limit: int,
        offset: int,
        columns: list[str] | None,
        filters: dict[str, str] | None,
        version: int | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if columns:
            params["columns"] = ",".join(columns)
        if version is not None:
            params["version"] = version
        for column, value in (filters or {}).items():
            params[f"filter[{column}]"] = value
        return params

    def _fetch(
        self,
        *,
        columns: list[str] | None,
        filters: dict[str, str] | None,
        max_rows: int | None,
        version: int | None,
    ) -> dict[str, Any]:
        """Page through the serve endpoint and return metadata plus rows."""
        serve_url = self.serve_url
        if not serve_url:
            msg = "Dataset Serve URL is required."
            raise ValueError(msg)

        rows: list[dict[str, Any]] = []
        meta: dict[str, Any] = {}
        offset = 0
        pinned_version = version
        while True:
            limit = PAGE_SIZE if max_rows is None else min(PAGE_SIZE, max_rows - len(rows))
            if limit <= 0:
                break
            try:
                response = ssrf_safe_httpx_get(
                    serve_url,
                    params=self._build_params(
                        limit=limit, offset=offset, columns=columns, filters=filters, version=pinned_version
                    ),
                    timeout=60,
                )
            except SSRFProtectionError as e:
                msg = f"SSRF Protection: {e}"
                raise ValueError(msg) from e
            response.raise_for_status()
            page = response.json()
            if not meta:
                meta = {
                    "dataset": page.get("dataset"),
                    "dataset_name": page.get("dataset_name"),
                    "table": page.get("table"),
                    "version": page.get("version"),
                    "updated_at": page.get("updated_at"),
                }
            if pinned_version is None:
                pinned_version = page.get("version")
            rows.extend(page.get("rows") or [])
            if max_rows is not None and len(rows) >= max_rows:
                del rows[max_rows:]
                break
            if not page.get("has_more") or page.get("next_offset") is None:
                break
            offset = page["next_offset"]

        return {**meta, "row_count": len(rows), "rows": rows}
