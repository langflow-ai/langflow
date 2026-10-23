"""Read rows from a Jsonify dataset.

Jsonify pipelines run on a schedule, repair themselves when a source changes,
and publish the result as a dataset. Each dataset has a serve URL that returns
its latest rows as JSON with paging, column selection, exact-match filters and
version pinning. The URL is the credential, so it is handled as a secret, never
exposed to the agent, and redacted from every error message.
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
from lfx.utils.ssrf_httpx import ssrf_safe_httpx_get_bounded
from lfx.utils.ssrf_protection import SSRFProtectionError
from pydantic import BaseModel, Field

PAGE_SIZE = 1000
MAX_PAGE_BYTES = 20 * 1024 * 1024
TOOL_MAX_ROWS = 10_000
MAX_FILTERS = 10
ROW_ID = "_row_id"
SYSTEM_COLUMNS = ("_parent_row_id", "_source_key")
REDACTED = "[REDACTED]"


class JsonifyFetchError(ValueError):
    """A fetch failure whose message never contains the serve URL."""


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
            info=(
                "Comma-separated column names to return, for example 'competitor, url'. Empty returns all. "
                "_row_id is always included. When used as a tool, the agent can only narrow this list."
            ),
        ),
        MultilineInput(
            name="filters",
            display_name="Filters",
            info=(
                "JSON object of exact, case-sensitive column matches combined with AND, "
                'for example {"competitor": "Klue"}. Up to 10 filters. '
                "When used as a tool, these always apply and the agent cannot override them."
            ),
            value="",
        ),
        IntInput(
            name="max_rows",
            display_name="Max rows",
            info=(
                "Maximum number of rows to return. 0 returns all matching rows. "
                f"When used as a tool, the agent's limit is capped by this value and by {TOOL_MAX_ROWS}."
            ),
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
            description=(
                "Extra exact, case-sensitive column matches combined with AND, for example {'competitor': 'Klue'}. "
                "Filters configured on the component always apply."
            ),
        )
        columns: list[str] = Field(
            default_factory=list,
            description="Column names to return. Empty returns the component's configured columns.",
        )
        max_rows: int = Field(100, ge=1, le=TOOL_MAX_ROWS, description="Maximum number of rows to return.")

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------

    def fetch_rows(self) -> list[Data]:
        """Return one Data object per row of the configured dataset."""
        result = self._fetch(**self._configured_query())
        data = [Data(data=row) for row in result["rows"]]
        self.status = data
        return data

    def fetch_dataframe(self) -> DataFrame:
        """Return the configured dataset's rows as a DataFrame."""
        result = self._fetch(**self._configured_query())
        frame = DataFrame(result["rows"])
        self.status = frame
        return frame

    def build_tool(self) -> Tool:
        """Build the agent tool; the serve URL and configured restrictions are not agent-controlled."""
        return StructuredTool.from_function(
            name="read_jsonify_dataset",
            description=(
                "Read rows from a maintained Jsonify dataset. Rows are current without scraping. "
                "Pass filters to match column values exactly and columns to limit the fields returned. "
                "The result says whether more rows matched than were returned (truncated)."
            ),
            func=self._run_for_tool,
            args_schema=self.ToolSchema,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _configured_query(self) -> dict[str, Any]:
        """Collect the query configured on the component, validating max_rows."""
        if self.max_rows is not None and self.max_rows < 0:
            msg = "Max rows must be 0 (all rows) or a positive number."
            raise ValueError(msg)
        return {
            "columns": self._parse_columns(self.columns),
            "filters": self._parse_filters(self.filters),
            "max_rows": self.max_rows or None,
            "version": self.version or None,
        }

    def _run_for_tool(
        self, filters: dict[str, str] | None = None, columns: list[str] | None = None, max_rows: int = 100
    ) -> str:
        """Agent entry point: merge agent arguments under the configured restrictions and return JSON."""
        try:
            configured = self._configured_query()
            merged_filters = {**(filters or {}), **(configured["filters"] or {})}
            if len(merged_filters) > MAX_FILTERS:
                msg = f"At most {MAX_FILTERS} filters are supported."
                raise ValueError(msg)
            allowed = configured["columns"]
            requested = [c for c in (columns or []) if c]
            if allowed and requested:
                requested = [c for c in requested if c in allowed]
            limit = max(1, min(max_rows, TOOL_MAX_ROWS))
            if configured["max_rows"]:
                limit = min(limit, configured["max_rows"])
            result = self._fetch(
                columns=requested or allowed,
                filters=merged_filters or None,
                max_rows=limit,
                version=configured["version"],
            )
        except (JsonifyFetchError, ValueError, TypeError) as e:
            return f"Error reading Jsonify dataset: {self._redact(str(e))}"
        return json.dumps(result, ensure_ascii=False)

    def _redact(self, text: str) -> str:
        """Remove the serve URL (the credential) from text."""
        serve_url = self.serve_url or ""
        return text.replace(serve_url, REDACTED) if serve_url else text

    @staticmethod
    def _parse_columns(value: str | None) -> list[str] | None:
        """Split a comma-separated column list."""
        if not value:
            return None
        columns = [c.strip() for c in value.split(",") if c.strip()]
        return columns or None

    @staticmethod
    def _parse_filters(value: str | None) -> dict[str, str] | None:
        """Parse the filters input as a JSON object of column name to value."""
        if not value or not value.strip():
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            msg = f"Filters must be valid JSON: {e.msg}"
            raise ValueError(msg) from e
        if not isinstance(parsed, dict):
            msg = "Filters must be a JSON object of column name to value."
            raise TypeError(msg)
        if len(parsed) > MAX_FILTERS:
            msg = f"At most {MAX_FILTERS} filters are supported."
            raise ValueError(msg)
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
        """Build serve URL query parameters; _row_id is always requested alongside selected columns."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if columns:
            selected = columns if ROW_ID in columns else [ROW_ID, *columns]
            params["columns"] = ",".join(selected)
        if version is not None:
            params["version"] = version
        for column, value in (filters or {}).items():
            params[f"filter[{column}]"] = value
        return params

    def _get_page(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch and validate one page, with a byte cap and URL-free errors."""
        try:
            body = ssrf_safe_httpx_get_bounded(self.serve_url, max_bytes=MAX_PAGE_BYTES, params=params, timeout=60)
        except SSRFProtectionError as e:
            msg = f"SSRF Protection: {self._redact(str(e))}"
            raise JsonifyFetchError(msg) from e
        except httpx.HTTPStatusError as e:
            msg = f"Jsonify returned HTTP {e.response.status_code}"
            raise JsonifyFetchError(msg) from e
        except httpx.HTTPError as e:
            msg = f"Could not reach Jsonify: {type(e).__name__}"
            raise JsonifyFetchError(msg) from e
        except ValueError as e:
            msg = f"Jsonify response exceeded {MAX_PAGE_BYTES} bytes"
            raise JsonifyFetchError(msg) from e
        try:
            page = json.loads(body)
        except json.JSONDecodeError as e:
            msg = "Jsonify returned a response that is not JSON"
            raise JsonifyFetchError(msg) from e
        rows = page.get("rows") if isinstance(page, dict) else None
        if not isinstance(page, dict) or not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            msg = "Jsonify returned an unexpected response shape"
            raise JsonifyFetchError(msg)
        return page

    def _fetch(
        self,
        *,
        columns: list[str] | None,
        filters: dict[str, str] | None,
        max_rows: int | None,
        version: int | None,
    ) -> dict[str, Any]:
        """Page through the serve endpoint and return metadata, rows and a truncated flag."""
        if not self.serve_url:
            msg = "Dataset Serve URL is required."
            raise ValueError(msg)

        rows: list[dict[str, Any]] = []
        meta: dict[str, Any] = {}
        offset = 0
        pinned_version = version
        truncated = False
        while True:
            limit = PAGE_SIZE if max_rows is None else min(PAGE_SIZE, max_rows - len(rows))
            page = self._get_page(
                self._build_params(limit=limit, offset=offset, columns=columns, filters=filters, version=pinned_version)
            )
            if not meta:
                meta = {key: page.get(key) for key in ("dataset", "dataset_name", "table", "version", "updated_at")}
            if pinned_version is None:
                pinned_version = page.get("version")
            page_rows = [{k: v for k, v in r.items() if k not in SYSTEM_COLUMNS} for r in page["rows"]]
            rows.extend(page_rows)
            has_more = bool(page.get("has_more"))
            next_offset = page.get("next_offset")
            if max_rows is not None and len(rows) >= max_rows:
                truncated = has_more or len(rows) > max_rows
                del rows[max_rows:]
                break
            # Stop on an empty page or a cursor that does not advance, so a misbehaving
            # endpoint cannot keep the loop alive.
            if not has_more or not page_rows or not isinstance(next_offset, int) or next_offset <= offset:
                break
            offset = next_offset

        return {**meta, "row_count": len(rows), "truncated": truncated, "rows": rows}
