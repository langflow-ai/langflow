"""List recent TestMu AI automation builds."""

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


class TestMuAIBuildsComponent(Component):
    """List the latest automation builds in a TestMu AI account, one row per build."""

    __test__ = False  # the name starts with "Test"; keep pytest from collecting it

    display_name = "TestMu AI Builds"
    description = (
        "List recent automation builds on TestMu AI (formerly LambdaTest) with their status and dashboard link."
    )
    documentation = DOCUMENTATION_URL
    icon = "TestMuAI"
    name = "TestMuAIBuilds"

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
            name="build_status",
            display_name="Status",
            info="Only return builds with this status, such as completed, running or error.",
            advanced=True,
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Max Builds",
            info="The number of builds to return, from 1 to 100.",
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
        Output(display_name="Table", name="dataframe", method="builds_dataframe"),
    ]

    def list_builds(self) -> list[Data]:
        """Return one ``Data`` per build, newest first."""
        params: dict[str, object] = {"limit": clamp_limit(self.limit)}
        status = str(self.build_status or "").strip()
        if status:
            params["status"] = status

        try:
            rows = fetch_rows(
                "/automation/api/v1/builds",
                username=self.username,
                access_key=self.access_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                params=params,
            )
        except TestMuAIAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return [Data(text=str(exc), data={"error": str(exc)})]

        data = [
            Data(
                text=f"{row.get('name') or 'Untitled build'} (build {row.get('build_id')}): {row.get('status_ind')}",
                data=row,
            )
            for row in rows
        ]
        self.status = data
        return data

    def builds_dataframe(self) -> DataFrame:
        return DataFrame(self.list_builds())
