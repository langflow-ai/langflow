"""Shared inputs and publish flow for the Upload-Post components."""

from __future__ import annotations

from typing import Any

import httpx
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, IntInput, MessageTextInput, MultiselectInput, SecretStrInput
from lfx.schema.data import Data
from lfx.utils.file_path_security import component_file_access_scopes, enforce_local_file_access

from lfx_uploadpost._client import (
    UploadPostClient,
    UploadPostError,
    new_request_id,
    results_text,
    summarize,
)

DOCS_URL = "https://docs.upload-post.com"
DEFAULT_WAIT_SECONDS = 300


def api_key_input() -> SecretStrInput:
    return SecretStrInput(
        name="upload_post_api_key",
        display_name="Upload-Post API Key",
        required=True,
        info="Your Upload-Post API key. Create one at https://app.upload-post.com.",
        password=True,
    )


def user_input() -> MessageTextInput:
    return MessageTextInput(
        name="user",
        display_name="Profile",
        required=True,
        info="Upload-Post profile whose connected social accounts post the content.",
    )


def platforms_input(options: list[str], default: list[str]) -> MultiselectInput:
    return MultiselectInput(
        name="platforms",
        display_name="Platforms",
        options=options,
        value=default,
        required=True,
        info="Platforms to publish to. Platforms not connected to the profile are reported as skipped.",
    )


def publishing_inputs() -> list:
    """Advanced inputs every publish component shares."""
    return [
        MessageTextInput(
            name="scheduled_date",
            display_name="Schedule At",
            advanced=True,
            info="Optional ISO-8601 date/time to publish later, e.g. 2026-10-01T09:00:00Z (at most 365 days ahead).",
        ),
        MessageTextInput(
            name="timezone",
            display_name="Timezone",
            advanced=True,
            info="Optional IANA timezone for Schedule At, e.g. Europe/Madrid. Defaults to UTC.",
        ),
        MessageTextInput(
            name="facebook_page_id",
            display_name="Facebook Page ID",
            advanced=True,
            info="Facebook Page to post to. Defaults to the page connected to the profile.",
        ),
        MessageTextInput(
            name="pinterest_board_id",
            display_name="Pinterest Board ID",
            advanced=True,
            info="Pinterest board to pin to. Required when publishing to Pinterest.",
        ),
        BoolInput(
            name="wait_for_result",
            display_name="Wait for Result",
            value=True,
            advanced=True,
            info="Poll until every platform finishes. Turn off to return right after the upload is accepted.",
        ),
        IntInput(
            name="wait_timeout",
            display_name="Wait Timeout (seconds)",
            value=DEFAULT_WAIT_SECONDS,
            advanced=True,
            range_spec=RangeSpec(min=0, max=1800, step=1, step_type="int"),
            info="How long to wait for results. The upload keeps going on Upload-Post after this.",
        ),
    ]


class UploadPostBaseComponent(Component):
    """Base class: builds the request, submits once, and reports per-platform results."""

    documentation = DOCS_URL
    icon = "Share2"
    endpoint = ""

    def _client(self) -> UploadPostClient:
        return UploadPostClient(self.upload_post_api_key)

    def _selected_platforms(self) -> list[str]:
        platforms = [p for p in (self.platforms or []) if isinstance(p, str) and p]
        if not platforms:
            msg = "Select at least one platform."
            raise ValueError(msg)
        if "pinterest" in platforms and not self._text("pinterest_board_id"):
            msg = "Pinterest needs a Pinterest Board ID."
            raise ValueError(msg)
        return platforms

    def _text(self, name: str) -> str:
        value = getattr(self, name, None)
        return value.strip() if isinstance(value, str) else ""

    def _local_file(self, path: str) -> str:
        """Resolve an uploaded file, confined to the storage dir in restricted mode."""
        return str(enforce_local_file_access(self.resolve_path(path), scope_ids=component_file_access_scopes(self)))

    def _common_fields(self) -> dict[str, Any]:
        user = self._text("user")
        if not user:
            msg = "Profile is required. Set it to the Upload-Post profile to post from."
            raise ValueError(msg)
        fields: dict[str, Any] = {"user": user, "platform[]": self._selected_platforms()}
        for name, field in (
            ("scheduled_date", "scheduled_date"),
            ("timezone", "timezone"),
            ("facebook_page_id", "facebook_page_id"),
            ("pinterest_board_id", "pinterest_board_id"),
        ):
            if self._text(name):
                fields[field] = self._text(name)
        return fields

    def build_request(self) -> tuple[dict[str, Any], list[tuple[str, str]]]:
        """Return ``(form_fields, [(file_field, local_path), ...])``. Implemented by subclasses."""
        raise NotImplementedError

    def _error(self, message: str, **extra: Any) -> Data:
        result = Data(text=message, data={"success": False, "error": message, **extra})
        self.status = result
        return result

    def _unconfirmed(self, request_id: str, reason: str, *, accepted: bool) -> Data:
        """Report an upload whose outcome could not be confirmed, keeping its request_id.

        ``accepted`` is True when the API answered the upload with a 2xx, so it is on
        Upload-Post; False when the connection failed and it may or may not be.
        """
        if accepted:
            text = (
                f"Uploaded, but the status check failed: {reason}. "
                f"Check request_id {request_id} with Upload-Post Status."
            )
            state = "submitted"
        else:
            text = (
                f"The upload could not be confirmed: {reason}. Check request_id {request_id} with "
                "Upload-Post Status before running this again; a new run is a new post."
            )
            state = "unknown"
        result = Data(
            text=text,
            data={"success": accepted, "status": state, "request_id": request_id, "error": reason, "results": []},
        )
        self.status = result
        return result

    def publish(self) -> Data:
        """Submit once, optionally wait, and return the per-platform results."""
        try:
            client = self._client()
            data, files = self.build_request()
            request_id = new_request_id()
            submitted = client.submit(self.endpoint, data, request_id, files)
        except (ValueError, OSError, UploadPostError) as e:
            return self._error(str(e))

        transport_error = submitted.get("transport_error")
        if self._text("scheduled_date"):
            job_id = submitted.get("job_id")
            if transport_error:
                # The server may have created the job before the connection dropped.
                try:
                    status = client.status(request_id=request_id)
                except (httpx.HTTPError, UploadPostError) as e:
                    return self._unconfirmed(request_id, f"{transport_error}; status check failed: {e}", accepted=False)
                if status.get("status") == "not_found":
                    return self._error(
                        f"Upload-Post has no record of request_id {request_id} yet ({transport_error}). "
                        "Check it again with Upload-Post Status in a minute before running this again.",
                        status="not_found",
                        request_id=request_id,
                    )
                job_id = status.get("job_id") or job_id
            summary = {
                "status": "scheduled",
                "request_id": submitted.get("request_id") or request_id,
                "job_id": job_id,
                "success": True,
                "timed_out": False,
                "results": [],
            }
            text = f"Scheduled (job {summary['job_id']}, request_id {summary['request_id']})."
        elif self.wait_for_result or transport_error:
            try:
                status = client.wait(request_id, float(self.wait_timeout or 0))
            except (httpx.HTTPError, UploadPostError) as e:
                return self._unconfirmed(request_id, str(e), accepted=not transport_error)
            if transport_error and status.get("status") == "not_found":
                return self._error(
                    f"Upload-Post has no record of request_id {request_id} yet ({transport_error}). "
                    "Check it again with Upload-Post Status in a minute before running this again.",
                    status="not_found",
                    request_id=request_id,
                )
            summary = summarize(status, request_id)
            text = results_text(summary)
        else:
            summary = {
                "status": "submitted",
                "request_id": request_id,
                "job_id": submitted.get("job_id"),
                "success": True,
                "timed_out": False,
                "results": [],
            }
            text = f"Submitted. Check it with the Upload-Post Status component, request_id {request_id}."

        result = Data(text=text, data=summary)
        self.status = result
        return result
