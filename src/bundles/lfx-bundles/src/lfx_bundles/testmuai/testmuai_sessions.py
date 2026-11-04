"""List TestMu AI automation test sessions, optionally for one build."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.testmuai.testmuai_common import (
    ACCESS_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    USERNAME_INFO,
    TestMuAIAPIError,
    clamp_limit,
    fetch_rows,
)


class TestMuAISessionsComponent(Component):
    """List automation test sessions with their status, environment and log links."""

    __test__ = False  # the name starts with "Test"; keep pytest from collecting it

    display_name = "TestMu AI Sessions"
    description = (
        "List automation test sessions on TestMu AI (formerly LambdaTest) with status, browser, platform "
        "and links to logs and video, to triage failed tests."
    )
    documentation = DOCUMENTATION_URL
    icon = "TestMuAI"
    name = "TestMuAISessions"

    inputs = [
        MessageTextInput(
            name="username",
            display_name="TestMu AI Username",
            info=USERNAME_INFO,
            required=True,
        ),
        SecretStrInput(
            name="access_key",
            display_name="TestMu AI Access Key",
            info=ACCESS_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="build_id",
            display_name="Build ID",
            info="Only return sessions from this build. Get build IDs from the TestMu AI Builds component.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="session_status",
            display_name="Status",
            info="Only return sessions with this status, such as passed, failed or error.",
            advanced=True,
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Max Sessions",
            info="The number of sessions to return, from 1 to 100.",
            value=10,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for TestMu AI to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="sessions_dataframe"),
    ]

    def list_sessions(self) -> list[Data]:
        """Return one ``Data`` per session, newest first."""
        params: dict[str, object] = {"limit": clamp_limit(self.limit)}
        build_id = str(self.build_id or "").strip()
        if build_id:
            if not build_id.isdigit():
                error = "Build ID must be a number."
                self.status = error
                return [Data(text=error, data={"error": error})]
            params["build_id"] = build_id
        status = str(self.session_status or "").strip()
        if status:
            params["status"] = status

        try:
            rows = fetch_rows(
                "/automation/api/v1/sessions",
                username=self.username,
                access_key=self.access_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                params=params,
            )
        except TestMuAIAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [Data(text=self._summary(row), data=row) for row in rows]
        self.status = data
        return data

    @staticmethod
    def _summary(row: dict) -> str:
        environment = " ".join(str(row.get(field) or "") for field in ("browser", "version")).strip()
        if row.get("platform"):
            environment = f"{environment} on {row['platform']}".strip()
        summary = f"{row.get('name') or 'Untitled test'}: {row.get('status_ind')}"
        if environment:
            summary += f" ({environment})"
        if row.get("remark"):
            summary += f" - {row['remark']}"
        return summary

    def sessions_dataframe(self) -> DataFrame:
        return DataFrame(self.list_sessions())
