"""Look up a GenMagic video job."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message

from lfx_bundles.genmagic.genmagic_common import (
    API_KEY_INFO,
    API_KEY_VARIABLE,
    DOCUMENTATION_URL,
    VIDEO_DONE_STATES,
    VIDEO_REQUEST_TIMEOUT_SECONDS,
    GenMagicAPIError,
    GenMagicVideoTimeoutError,
    call_api,
    metering,
    positive_seconds,
    response_json,
    text_value,
    video_path,
    video_result,
    wait_for_video,
)

DEFAULT_POLL_SECONDS = 5.0


class GenMagicVideoStatusComponent(Component):
    """Check a video job started by GenMagic Video Generation, optionally waiting for it to finish."""

    display_name = "GenMagic Video Status"
    description = "Look up a GenMagic video job by ID, for example one that was still rendering when a timeout passed."
    documentation = DOCUMENTATION_URL
    icon = "GenMagic"
    name = "GenMagicVideoStatus"

    # The request and result of this build, shared by every connected output (see _pre_run_setup).
    _lookup: tuple[str, dict[str, Any]] | None = None

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="GenMagic API Key",
            info=API_KEY_INFO,
            value=API_KEY_VARIABLE,
            required=True,
        ),
        MessageTextInput(
            name="job_id",
            display_name="Job ID",
            info="The ID of the video job, from the Result of GenMagic Video Generation or from its timeout error.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="wait",
            display_name="Wait (seconds)",
            info="How long to keep checking until the video is done. Leave at 0 to look the job up once. "
            "Looking up a job spends no credits.",
            value=0,
            advanced=True,
        ),
        FloatInput(
            name="poll_interval",
            display_name="Poll Interval (seconds)",
            info="How often to check while waiting.",
            value=DEFAULT_POLL_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Video URL", name="video_url", method="build_video_url", tool_mode=False),
        Output(display_name="Result", name="result", method="build_result"),
    ]

    def _pre_run_setup(self) -> None:
        self._lookup = None

    def lookup(self) -> dict[str, Any]:
        """Return the job's ``status`` and, once it has completed, the hosted ``url`` and cost."""
        job_id = text_value(self.job_id)
        if not job_id:
            msg = "Enter the ID of the video job."
            raise GenMagicAPIError(msg)
        cached = self._lookup
        if cached is not None and cached[0] == job_id:
            return cached[1]
        response = call_api("GET", video_path(job_id), api_key=self.api_key, timeout=VIDEO_REQUEST_TIMEOUT_SECONDS)
        job, costs = response_json(response), metering(response)
        wait = positive_seconds(self.wait, 0)
        if wait and job.get("status") not in VIDEO_DONE_STATES:
            try:
                # The lookup may answer without the job's own id; the person already gave it, so poll with that one.
                job, costs = wait_for_video(
                    {**job, "id": job.get("id") or job_id},
                    api_key=self.api_key,
                    timeout=wait,
                    poll_interval=positive_seconds(self.poll_interval, DEFAULT_POLL_SECONDS),
                )
            except GenMagicVideoTimeoutError as exc:
                # Still rendering after the wait is an answer, not an error: report the job as it stands.
                job, costs = exc.job, exc.costs
        result = video_result(job, costs)
        result.setdefault("id", job_id)
        self._lookup = (job_id, result)
        self.status = str(result.get("status", ""))
        return result

    def build_video_url(self) -> Message:
        """The hosted URL of the clip, or empty text while the job has not completed."""
        return Message(text=str(self.lookup().get("url", "")))

    def build_result(self) -> Data:
        """The job's ID, status, model and, when it has completed, the URL and cost; or the error if it failed."""
        return Data(data=self.lookup())
