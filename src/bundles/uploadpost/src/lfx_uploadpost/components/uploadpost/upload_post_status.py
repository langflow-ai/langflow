"""Upload-Post: check the per-platform status of an upload."""

from __future__ import annotations

import re

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data
from lfx_uploadpost._base import DOCS_URL, api_key_input
from lfx_uploadpost._client import UploadPostClient, UploadPostError, results_text, summarize

# Scheduled job ids are 32 hex characters; request ids (UUIDs) are not.
JOB_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


class UploadPostStatusComponent(Component):
    display_name = "Upload-Post Status"
    description = "Check the per-platform result of an Upload-Post upload by request_id or scheduled job_id."
    documentation = DOCS_URL
    icon = "Share2"
    name = "UploadPostStatus"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="upload_id",
            display_name="Request or Job ID",
            required=True,
            info="The request_id returned by a publish component, or the job_id of a scheduled post.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="upload_post_status"),
    ]

    def upload_post_status(self) -> Data:
        upload_id = (self.upload_id or "").strip()
        try:
            client = UploadPostClient(self.upload_post_api_key)
            if not upload_id:
                msg = "Request or Job ID is required."
                raise ValueError(msg)
            kinds = ["job_id", "request_id"] if JOB_ID_PATTERN.fullmatch(upload_id) else ["request_id", "job_id"]
            for kind in kinds:
                status = client.status(**{kind: upload_id})
                if status.get("status") != "not_found":
                    break
        except (ValueError, httpx.HTTPError, UploadPostError) as e:
            message = str(e)
            result = Data(text=message, data={"success": False, "error": message})
            self.status = result
            return result
        summary = summarize(status, upload_id if kinds[0] == "request_id" else None)
        text = results_text(summary)
        if summary["status"] == "not_found":
            text = f"No Upload-Post upload found with id {upload_id}."
        result = Data(text=text, data=summary)
        self.status = result
        return result
