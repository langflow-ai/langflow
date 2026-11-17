"""Judge a program against test cases with OnlineCompiler.io."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.onlinecompiler.onlinecompiler_common import (
    API_KEY_INFO,
    CHECKERS,
    COMPILER_INFO,
    DEFAULT_COMPILER,
    DOCUMENTATION_URL,
    RUN_TESTS_TIMEOUT_SECONDS,
    SCORINGS,
    OnlineCompilerAPIError,
    onlinecompiler_post,
    parse_tests,
)


def tests_summary(result: dict) -> str:
    """Return the overall verdict and score, then one line per test."""
    verdict, passed, total = result.get("verdict"), result.get("passed"), result.get("total")
    lines = [f"{verdict}: {passed} of {total} tests passed, score {result.get('score')}"]
    for number, test in enumerate(result.get("tests") or [], start=1):
        if not isinstance(test, dict):
            continue
        line = f"test {number}: {test.get('verdict')}"
        if test.get("hidden"):
            line += " (hidden)"
        lines.append(line)
    return "\n".join(lines)


class OnlineCompilerRunTestsComponent(Component):
    """Judge a program against test cases through OnlineCompiler.io.

    The program runs once per test, each run in a fresh gVisor sandbox with no network,
    and its output is compared with the expected output. The answer has an overall
    verdict, a score from 0 to 100 and a verdict for each test. Each test counts as one run.
    """

    display_name = "OnlineCompiler.io Run Tests"
    description = "Judge code against test cases in 46 languages: an overall verdict, a score and a verdict per test."
    documentation = DOCUMENTATION_URL
    icon = "SquareTerminal"
    name = "OnlineCompilerRunTests"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="OnlineCompiler.io API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="compiler",
            display_name="Language",
            info=COMPILER_INFO,
            value=DEFAULT_COMPILER,
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="source_code",
            display_name="Code",
            info="The whole program to judge. It reads each test's input as standard input.",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="tests",
            display_name="Tests",
            info='A JSON array of tests, such as [{"input": "2 3", "expected_output": "5"}].',
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="checker",
            display_name="Compare",
            info=(
                "How output is compared: trim ignores trailing whitespace, tokens ignores all whitespace, "
                "float compares numbers within a tolerance, rows ignores line order, "
                "table and table_ordered compare CSV tables by column name."
            ),
            options=CHECKERS,
            value="trim",
            advanced=True,
        ),
        DropdownInput(
            name="scoring",
            display_name="Scoring",
            info="percent scores the share of tests passed; all_or_nothing scores 100 only when every test passes.",
            options=SCORINGS,
            value="percent",
            advanced=True,
        ),
        FloatInput(
            name="time_limit",
            display_name="Time Limit (seconds)",
            info="Seconds each test may run, up to 30. 0 uses the default.",
            value=0.0,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for OnlineCompiler.io to answer.",
            value=RUN_TESTS_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Verdict", name="verdict", method="run_tests"),
    ]

    async def run_tests(self) -> Data:
        """Return a short verdict summary as ``text`` and the whole result as data."""
        try:
            compiler = str(self.compiler or "").strip()
            source = str(self.source_code or "")
            if not compiler:
                msg = "Enter a language, such as python-3.14."
                raise OnlineCompilerAPIError(msg)
            if not source.strip():
                msg = "Enter the code to judge."
                raise OnlineCompilerAPIError(msg)
            payload: dict = {
                "compiler": compiler,
                "code": source,
                "tests": parse_tests(self.tests),
                "checker": self.checker if self.checker in CHECKERS else "trim",
                "scoring": self.scoring if self.scoring in SCORINGS else "percent",
            }
            if self.time_limit and float(self.time_limit) > 0:
                payload["time_limit"] = float(self.time_limit)
            result = await onlinecompiler_post(
                "/api/run-tests/",
                api_key=self.api_key,
                payload=payload,
                timeout=float(self.timeout or RUN_TESTS_TIMEOUT_SECONDS),
            )
        except OnlineCompilerAPIError as exc:
            await logger.aerror(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"api_error": str(exc)})

        data = Data(text=tests_summary(result), data=result)
        self.status = data
        return data
