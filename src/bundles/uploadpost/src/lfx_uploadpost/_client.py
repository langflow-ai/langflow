"""Minimal Upload-Post API client shared by the bundle's components.

Upload-Post (https://upload-post.com) publishes one piece of content to many
social platforms in a single call. The components talk to its REST API
directly with ``httpx`` and a user-supplied API key, so the bundle carries no
vendor SDK dependency. API reference: https://docs.upload-post.com.

Publishing is asynchronous: the client submits with ``async_upload=true`` and
its own ``request_id`` (also sent as ``Idempotency-Key``), then polls the
status endpoint. A transport error during the submit never re-sends the
request -- the server may already have it -- the caller checks the same
``request_id`` instead. That protects a single run; running a component
again is a new request and a new post.
"""

from __future__ import annotations

import time
import uuid
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import httpx

API_BASE = "https://api.upload-post.com"
USER_AGENT = "langflow-uploadpost-bundle"

VIDEO_PLATFORMS = ["tiktok", "instagram", "youtube", "linkedin", "facebook", "x", "threads", "pinterest", "bluesky"]
PHOTO_PLATFORMS = ["tiktok", "instagram", "linkedin", "facebook", "x", "threads", "pinterest", "bluesky"]
TEXT_PLATFORMS = ["x", "linkedin", "facebook", "threads", "bluesky"]

YOUTUBE_PRIVACY = ["private", "unlisted", "public"]
TIKTOK_PRIVACY = ["account default", "PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"]

FINAL_STATUSES = {"completed", "failed", "not_found"}
SUBMIT_TIMEOUT = httpx.Timeout(30.0, read=900.0)  # the read covers sending the media
API_TIMEOUT = httpx.Timeout(30.0)
POLL_INTERVAL_SECONDS = 5.0


class UploadPostError(Exception):
    """An Upload-Post API call failed with an HTTP error."""


def new_request_id() -> str:
    return str(uuid.uuid4())


def _error_message(response: httpx.Response) -> str:
    """Describe a non-2xx response, keeping the API's own message."""
    detail = None
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get("message") or payload.get("error")
    except ValueError:
        detail = None
    reason = detail or response.reason_phrase or "request failed"
    return f"Upload-Post API error {response.status_code}: {reason}"


class UploadPostClient:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            msg = "Upload-Post API key is required. Set the Upload-Post API Key input."
            raise ValueError(msg)
        self._headers = {
            # Upload-Post API keys use the "Apikey" scheme, not "Bearer".
            "Authorization": f"Apikey {api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

    def submit(
        self,
        endpoint: str,
        data: dict[str, Any],
        request_id: str,
        files: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """POST an upload. ``files`` is a list of ``(form_field, local_path)``.

        Returns the API response, or ``{"request_id": ..., "transport_error": ...}``
        when the outcome is ambiguous -- the connection failed or the API answered
        5xx -- and the upload may or may not have arrived. A 4xx is a definitive
        rejection and raises ``UploadPostError``.
        """
        form = {**data, "request_id": request_id, "async_upload": "true"}
        headers = {**self._headers, "Idempotency-Key": request_id}
        try:
            with ExitStack() as stack:
                multipart = [
                    (field, (Path(path).name, stack.enter_context(Path(path).open("rb"))))
                    for field, path in (files or [])
                ]
                response = httpx.post(
                    f"{API_BASE}{endpoint}",
                    headers=headers,
                    data=form,
                    files=multipart or None,
                    timeout=SUBMIT_TIMEOUT,
                )
        except httpx.TransportError as e:
            # Do not resend: poll this request_id to learn whether it arrived.
            return {"request_id": request_id, "transport_error": str(e)}
        if response.is_server_error:
            # A 5xx doesn't say whether the upload was stored; treat it like a
            # dropped connection and let the caller check the request_id.
            return {"request_id": request_id, "transport_error": _error_message(response)}
        if response.is_error:
            raise UploadPostError(_error_message(response))
        try:
            payload = response.json()
        except ValueError:
            # A 2xx means the upload was accepted even if the body is empty or not JSON.
            return {"request_id": request_id}
        return payload if isinstance(payload, dict) else {"request_id": request_id}

    def status(self, *, request_id: str | None = None, job_id: str | None = None) -> dict[str, Any]:
        params = {"job_id": job_id} if job_id else {"request_id": request_id}
        response = httpx.get(
            f"{API_BASE}/api/uploadposts/status",
            headers=self._headers,
            params=params,
            timeout=API_TIMEOUT,
        )
        if response.status_code == httpx.codes.NOT_FOUND:
            return {"status": "not_found", **params}
        if response.is_error:
            raise UploadPostError(_error_message(response))
        payload = response.json()
        return payload if isinstance(payload, dict) else {"status": "unknown", **params}

    def wait(self, request_id: str, timeout_seconds: float) -> dict[str, Any]:
        """Poll until every platform finishes or ``timeout_seconds`` passes."""
        deadline = time.monotonic() + max(timeout_seconds, 0)
        while True:
            status = self.status(request_id=request_id)
            if status.get("status") in FINAL_STATUSES:
                return status
            if time.monotonic() >= deadline:
                return {**status, "timed_out": True}
            time.sleep(POLL_INTERVAL_SECONDS)


def platform_results(status: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize per-platform results to ``{platform, status, url, post_id, note, error}``."""
    raw = status.get("results") or []
    if isinstance(raw, dict):  # synchronous shape: {"tiktok": {...}}
        raw = [{"platform": name, **(value or {})} for name, value in raw.items()]
    results = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("skipped"):
            state = "skipped"
        elif item.get("status"):
            state = str(item["status"])
        else:
            state = "completed" if item.get("success") else "failed"
        post_url = item.get("post_url") or item.get("url")
        url = post_url if isinstance(post_url, str) and post_url.startswith("http") else None
        results.append(
            {
                "platform": item.get("platform"),
                "status": state,
                "url": url,
                "post_id": item.get("platform_post_id"),
                # A private post has no public link; the API explains why in post_url.
                "note": post_url if post_url and not url else None,
                "error": (item.get("error_message") or item.get("error")) if state != "completed" else None,
            }
        )
    return results


def summarize(status: dict[str, Any], request_id: str | None) -> dict[str, Any]:
    """Build the component output from a status payload."""
    results = platform_results(status)
    state = status.get("status")
    failed = [r for r in results if r["status"] in {"failed", "retryable"}]
    published = [r for r in results if r["status"] == "completed"]
    return {
        "status": state,
        "request_id": status.get("request_id") or request_id,
        "job_id": status.get("job_id"),
        "success": state != "not_found" and not failed and (bool(published) or state not in FINAL_STATUSES),
        "timed_out": bool(status.get("timed_out")),
        "results": results,
    }


def results_text(summary: dict[str, Any]) -> str:
    """One line per platform, readable by a person or an agent."""
    lines = []
    for r in summary["results"]:
        detail = r["url"] or r["error"] or r["note"] or (f"post id {r['post_id']}" if r["post_id"] else "")
        lines.append(f"{r['platform']}: {r['status']}" + (f" - {detail}" if detail else ""))
    if summary["timed_out"]:
        lines.append(f"Still running; check it later with request_id {summary['request_id']}.")
    if not lines:
        lines.append(f"Upload-Post status: {summary['status']} (request_id {summary['request_id']}).")
    return "\n".join(lines)
