"""Thin httpx helpers shared by the Magic Hour components.

Talks to the Magic Hour REST API (https://docs.magichour.ai) directly so the
bundle needs no third-party SDK beyond ``httpx`` (an lfx core dependency).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

MAGIC_HOUR_API_BASE = "https://api.magichour.ai/v1"
DEFAULT_TIMEOUT = 60.0
TERMINAL_STATUSES = {"complete", "error", "canceled"}


class MagicHourError(RuntimeError):
    """Raised when the Magic Hour API returns an error or a job fails."""


def _headers(api_key: str) -> dict[str, str]:
    if not api_key:
        msg = "A Magic Hour API key is required. Get one at https://magichour.ai/developer."
        raise MagicHourError(msg)
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        detail = response.json()
    except ValueError:
        detail = response.text
    msg = f"Magic Hour API error {response.status_code}: {detail}"
    raise MagicHourError(msg)


def create_project(api_key: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST ``/v1/<endpoint>`` and return the ``{id, credits_charged}`` response body."""
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.post(f"{MAGIC_HOUR_API_BASE}/{endpoint}", json=payload, headers=_headers(api_key))
    _raise_for_status(response)
    return response.json()


def get_project(api_key: str, kind: str, project_id: str) -> dict[str, Any]:
    """GET ``/v1/<kind>-projects/{id}``; ``kind`` is ``"video"`` or ``"image"``."""
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.get(f"{MAGIC_HOUR_API_BASE}/{kind}-projects/{project_id}", headers=_headers(api_key))
    _raise_for_status(response)
    return response.json()


def wait_for_project(
    api_key: str,
    kind: str,
    project_id: str,
    *,
    poll_interval: float = 5.0,
    timeout: float = 600.0,
) -> dict[str, Any]:
    """Poll a project until it reaches a terminal status or ``timeout`` seconds elapse."""
    deadline = time.monotonic() + timeout
    while True:
        project = get_project(api_key, kind, project_id)
        status = project.get("status")
        if status in TERMINAL_STATUSES:
            if status != "complete":
                error = project.get("error") or {}
                msg = f"Magic Hour {kind} project {project_id} ended with status '{status}': {error}"
                raise MagicHourError(msg)
            return project
        if time.monotonic() >= deadline:
            msg = (
                f"Timed out after {timeout:.0f}s waiting for Magic Hour {kind} project {project_id} (status={status})."
            )
            raise MagicHourError(msg)
        time.sleep(poll_interval)


def download_urls(project: dict[str, Any]) -> list[str]:
    return [item["url"] for item in project.get("downloads", []) if item.get("url")]


def upload_local_file(api_key: str, path: str) -> str:
    """Upload a local image via ``/v1/files/upload-urls`` and return the Magic Hour ``file_path``."""
    file_path = Path(path)
    if not file_path.is_file():
        msg = f"Image file not found: {path}"
        raise MagicHourError(msg)
    extension = file_path.suffix.lstrip(".").lower() or "png"
    response = create_project(api_key, "files/upload-urls", {"items": [{"extension": extension, "type": "image"}]})
    item = response["items"][0]
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        put = client.put(item["upload_url"], content=file_path.read_bytes())
    _raise_for_status(put)
    return item["file_path"]


def resolve_image_asset(api_key: str, image: str) -> str:
    """Return something ``assets.image_file_path`` accepts: a public URL, an ``api-assets/`` path, or an upload."""
    image = (image or "").strip()
    if not image:
        msg = "An image URL or local file path is required."
        raise MagicHourError(msg)
    if image.startswith(("http://", "https://", "api-assets/")):
        return image
    return upload_local_file(api_key, image)
