"""Run a program in a fresh sandbox with OnlineCompiler.io."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.onlinecompiler.onlinecompiler_common import (
    API_KEY_INFO,
    COMPILER_INFO,
    DEFAULT_COMPILER,
    DOCUMENTATION_URL,
    RUN_CODE_TIMEOUT_SECONDS,
    OnlineCompilerAPIError,
    onlinecompiler_post,
)


def run_summary(result: dict) -> str:
    """Return the program's output, then its standard error and a non-zero exit code if any."""
    text = str(result.get("output") or "")
    error = str(result.get("error") or "")
    if error:
        text += ("\n" if text and not text.endswith("\n") else "") + f"stderr:\n{error}"
    exit_code = result.get("exit_code")
    if exit_code not in (0, None):
        text += ("\n" if text and not text.endswith("\n") else "") + f"exit code: {exit_code}"
    return text


class OnlineCompilerRunCodeComponent(Component):
    """Run code in 46 languages through OnlineCompiler.io.

    Each run starts in a fresh gVisor sandbox with no network, a 30 second limit and
    512 MB of memory, so it is safe for code an agent or a user wrote. Only the code,
    the language and the input are sent to ``api.onlinecompiler.io``.
    """

    display_name = "OnlineCompiler.io Run Code"
    description = "Run code in 46 languages in a fresh sandbox with no network, and get its output and exit code."
    documentation = DOCUMENTATION_URL
    icon = "SquareTerminal"
    name = "OnlineCompilerRunCode"

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
            info="The whole program to run.",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="stdin",
            display_name="Input",
            info="Text the program reads as standard input. Leave empty if it reads none.",
            tool_mode=True,
        ),
        FloatInput(
            name="time_limit",
            display_name="Time Limit (seconds)",
            info="Seconds the program may run, up to 30. 0 uses the default.",
            value=0.0,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for OnlineCompiler.io to answer.",
            value=RUN_CODE_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run_code"),
    ]

    async def run_code(self) -> Data:
        """Return the output as ``text`` and the whole result (output, error, exit_code, time, memory) as data."""
        try:
            compiler = str(self.compiler or "").strip()
            source = str(self.source_code or "")
            if not compiler:
                msg = "Enter a language, such as python-3.14."
                raise OnlineCompilerAPIError(msg)
            if not source.strip():
                msg = "Enter the code to run."
                raise OnlineCompilerAPIError(msg)
            payload: dict = {"compiler": compiler, "code": source}
            stdin = str(self.stdin or "")
            if stdin:
                payload["input"] = stdin
            if self.time_limit and float(self.time_limit) > 0:
                payload["time_limit"] = float(self.time_limit)
            result = await onlinecompiler_post(
                "/api/run-code-sync/",
                api_key=self.api_key,
                payload=payload,
                timeout=float(self.timeout or RUN_CODE_TIMEOUT_SECONDS),
            )
        except OnlineCompilerAPIError as exc:
            await logger.aerror(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"api_error": str(exc)})

        data = Data(text=run_summary(result), data=result)
        self.status = data
        return data
