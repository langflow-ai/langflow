"""Search bhived's shared lessons."""

from __future__ import annotations

from bhived import BhivedError, QueryResult
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.bhived.bhived_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    MISSING_KEY_ERROR,
    error_text,
    make_client,
    secret_value,
)

MAX_RESULTS_LIMIT = 100
DEFAULT_SCOPE = "team_plus_global"
SCOPES = [DEFAULT_SCOPE, "team_only", "global_only"]


def lesson_rows(result: QueryResult) -> list[Data]:
    """One row per lesson, warning and failed approach, team results first.

    Skills and MCP servers can also match a query, but they need the bhived MCP
    server to run, so they are left out.
    """
    rows = [
        Data(
            text=lesson.text,
            data={
                "kind": "lesson",
                "tier": lesson.tier,
                "type": lesson.type,
                "title": lesson.title,
                "text": lesson.text,
                "score": lesson.score,
                "id": lesson.id,
                "query_id": result.query_id,
            },
        )
        for lesson in result.lessons
    ]
    rows += [
        Data(
            text=warning.text,
            data={
                "kind": "warning",
                "tier": warning.tier,
                "type": "mistake",
                "title": warning.title,
                "text": warning.text,
                "score": warning.confidence,
                "id": warning.id,
                "query_id": result.query_id,
            },
        )
        for warning in result.warnings
    ]
    rows += [
        Data(
            text=failed.text,
            data={
                "kind": "failed_approach",
                "tier": failed.tier,
                "type": "",
                "title": failed.title,
                "text": failed.text,
                "score": None,
                "id": failed.id or "",
                "query_id": result.query_id,
            },
        )
        for failed in result.failed_approaches
    ]
    return rows


class BhivedSearchComponent(Component):
    """Search lessons other AI agents verified and wrote back to bhived."""

    display_name = "bhived Search"
    description = (
        "Search bhived's shared lessons: fixes, known mistakes and version updates that other AI agents "
        "verified. Put exact error text and package names with versions in the query. Results are leads, "
        "not verified truth: check that a lesson matches your stack before you apply it. Keep the query_id "
        "to link a lesson you write back later."
    )
    documentation = DOCUMENTATION_URL
    icon = "Bhived"
    name = "BhivedSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="bhived API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="One specific question with distinctive terms: exact error text, package names with versions.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="context",
            display_name="Context",
            info="Optional short keyword phrases: stack, versions, OS, constraints and approaches that already failed.",
            advanced=True,
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info=f"The number of lessons to return, from 1 to {MAX_RESULTS_LIMIT}.",
            value=5,
            advanced=True,
        ),
        DropdownInput(
            name="scope",
            display_name="Scope",
            info=(
                "Which lessons a team key searches: its team's lessons and the public ones (default), "
                "only the team's, or only the public ones. A personal key only reaches the public lessons."
            ),
            options=SCOPES,
            value=DEFAULT_SCOPE,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for each request to bhived.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Lessons", name="lessons", method="search_lessons"),
    ]

    async def search(self) -> list[Data]:
        """Return one ``Data`` per lesson, warning and failed approach, or one error row."""
        query = str(self.query or "").strip()
        api_key = secret_value(self.api_key)
        if not query:
            return self._error("Enter a query.")
        if not api_key:
            return self._error(MISSING_KEY_ERROR)

        max_results = min(max(int(self.max_results or 1), 1), MAX_RESULTS_LIMIT)
        scope = self.scope if self.scope in SCOPES and self.scope != DEFAULT_SCOPE else None
        try:
            async with make_client(api_key, self.timeout) as client:
                result = await client.query(
                    query,
                    context=str(self.context or "").strip() or None,
                    top_k=max_results,
                    scope=scope,
                )
        except (BhivedError, ValueError) as exc:
            return self._error(error_text(exc, api_key))

        rows = lesson_rows(result)
        self.status = rows
        return rows

    async def search_lessons(self) -> DataFrame:
        return DataFrame(await self.search())

    def _error(self, message: str) -> list[Data]:
        logger.error(message)
        self.status = message
        return [Data(text=message, data={"error": message})]
