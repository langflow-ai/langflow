"""Unit tests for the Upload-Post extension bundle (``lfx-uploadpost``).

The components call the Upload-Post REST API with ``httpx``; the tests patch
``httpx.post`` / ``httpx.get`` in the client module to return real
``httpx.Response`` objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_uploadpost import (
    UploadPostPhotosComponent,
    UploadPostStatusComponent,
    UploadPostTextComponent,
    UploadPostVideoComponent,
    _client,
)

POST_TARGET = "lfx_uploadpost._client.httpx.post"
GET_TARGET = "lfx_uploadpost._client.httpx.get"
BASE = "https://api.upload-post.com"

COMPLETED = {
    "status": "completed",
    "completed": 2,
    "total": 2,
    "results": [
        {
            "platform": "youtube",
            "success": True,
            "platform_post_id": "abc123",
            "post_url": "Post uploaded as Private. No public URL available.",
        },
        {"platform": "tiktok", "success": True, "post_url": "https://www.tiktok.com/@a/video/1"},
    ],
}


def _response(status_code: int = 200, method: str = "POST", url: str = f"{BASE}/api/upload", **kwargs):
    return httpx.Response(status_code, request=httpx.Request(method, url), **kwargs)


def _status_response(payload: dict, status_code: int = 200):
    return _response(status_code, "GET", f"{BASE}/api/uploadposts/status", json=payload)


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("lfx_uploadpost._client.time.sleep"):
        yield


def _video(**overrides) -> UploadPostVideoComponent:
    c = UploadPostVideoComponent()
    values = {
        "upload_post_api_key": "test-key",  # pragma: allowlist secret
        "user": "creator",
        "platforms": ["tiktok", "youtube"],
        "video_file": None,
        "video_url": "https://example.com/v.mp4",
        "title": "My short",
        "description": "",
        "youtube_privacy": "private",
        "tiktok_privacy": "account default",
        "scheduled_date": "",
        "timezone": "",
        "facebook_page_id": "",
        "pinterest_board_id": "",
        "wait_for_result": True,
        "wait_timeout": 300,
    }
    values.update(overrides)
    for key, value in values.items():
        setattr(c, key, value)
    return c


def test_component_class_names_are_stable():
    """Class names back the migration table entries and saved flows."""
    names = [
        UploadPostVideoComponent.__name__,
        UploadPostPhotosComponent.__name__,
        UploadPostTextComponent.__name__,
        UploadPostStatusComponent.__name__,
    ]
    assert names == [
        "UploadPostVideoComponent",
        "UploadPostPhotosComponent",
        "UploadPostTextComponent",
        "UploadPostStatusComponent",
    ]


def test_missing_api_key_is_an_error_without_request():
    c = _video(upload_post_api_key="")
    post = MagicMock()
    with patch(POST_TARGET, post):
        result = c.upload_post_publish_video()
    post.assert_not_called()
    assert result.data["success"] is False
    assert "API key is required" in result.data["error"]


def test_video_request_fields_and_headers():
    """One POST with Apikey auth, Idempotency-Key == request_id, async, platforms as a list."""
    post = MagicMock(return_value=_response(json={"success": True}))
    get = MagicMock(return_value=_status_response(COMPLETED))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video(tiktok_privacy="SELF_ONLY").upload_post_publish_video()

    assert post.call_count == 1
    assert post.call_args.args[0] == f"{BASE}/api/upload"
    headers = post.call_args.kwargs["headers"]
    data = post.call_args.kwargs["data"]
    assert headers["Authorization"] == "Apikey test-key"  # pragma: allowlist secret
    assert headers["Idempotency-Key"] == data["request_id"]
    assert data["async_upload"] == "true"
    assert data["platform[]"] == ["tiktok", "youtube"]
    assert data["video"] == "https://example.com/v.mp4"
    assert data["privacyStatus"] == "private"
    assert data["privacy_level"] == "SELF_ONLY"
    assert get.call_args.kwargs["params"] == {"request_id": data["request_id"]}
    assert result.data["success"] is True


def test_youtube_defaults_to_private_and_tiktok_keeps_account_default():
    post = MagicMock(return_value=_response(json={}))
    with patch(POST_TARGET, post), patch(GET_TARGET, MagicMock(return_value=_status_response(COMPLETED))):
        _video().upload_post_publish_video()
    data = post.call_args.kwargs["data"]
    assert data["privacyStatus"] == "private"
    assert "privacy_level" not in data


def test_video_results_are_normalized():
    """Private posts have no public URL: YouTube keeps the post id and the API's note."""
    post = MagicMock(return_value=_response(json={}))
    with patch(POST_TARGET, post), patch(GET_TARGET, MagicMock(return_value=_status_response(COMPLETED))):
        result = _video().upload_post_publish_video()
    by_platform = {r["platform"]: r for r in result.data["results"]}
    assert by_platform["youtube"]["status"] == "completed"
    assert by_platform["youtube"]["url"] is None
    assert by_platform["youtube"]["post_id"] == "abc123"
    assert "Private" in by_platform["youtube"]["note"]
    assert by_platform["tiktok"]["url"] == "https://www.tiktok.com/@a/video/1"
    assert "tiktok: completed - https://www.tiktok.com/@a/video/1" in result.text


def test_transport_error_never_resends_and_polls_the_same_request_id():
    """A dropped connection mid-upload must not double-post."""
    post = MagicMock(side_effect=httpx.ReadTimeout("timed out"))
    get = MagicMock(return_value=_status_response(COMPLETED))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video(wait_for_result=False).upload_post_publish_video()
    assert post.call_count == 1
    sent_id = post.call_args.kwargs["data"]["request_id"]
    assert get.call_args.kwargs["params"] == {"request_id": sent_id}
    assert result.data["success"] is True


def test_failed_and_skipped_platforms():
    payload = {
        "status": "completed",
        "results": [
            {"platform": "tiktok", "success": True, "post_url": "https://t/1"},
            {"platform": "x", "success": False, "error_message": "boom"},
            {"platform": "linkedin", "success": False, "skipped": True},
        ],
    }
    with (
        patch(POST_TARGET, MagicMock(return_value=_response(json={}))),
        patch(GET_TARGET, MagicMock(return_value=_status_response(payload))),
    ):
        result = _video(platforms=["tiktok", "x", "linkedin"]).upload_post_publish_video()
    states = {r["platform"]: (r["status"], r["error"]) for r in result.data["results"]}
    assert states == {"tiktok": ("completed", None), "x": ("failed", "boom"), "linkedin": ("skipped", None)}
    assert result.data["success"] is False


def test_wait_timeout_reports_still_running():
    running = {"status": "processing", "completed": 0, "total": 1, "results": []}
    with (
        patch(POST_TARGET, MagicMock(return_value=_response(json={}))),
        patch(GET_TARGET, MagicMock(return_value=_status_response(running))),
    ):
        result = _video(wait_timeout=0).upload_post_publish_video()
    assert result.data["timed_out"] is True
    assert result.data["success"] is True
    assert "Still running" in result.text


def test_no_wait_returns_request_id_without_polling():
    get = MagicMock()
    with patch(POST_TARGET, MagicMock(return_value=_response(json={}))), patch(GET_TARGET, get):
        result = _video(wait_for_result=False).upload_post_publish_video()
    get.assert_not_called()
    assert result.data["status"] == "submitted"
    assert result.data["request_id"]


def test_scheduled_post_returns_job_id_without_polling():
    get = MagicMock()
    post = MagicMock(return_value=_response(202, json={"success": True, "job_id": "a" * 32}))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video(scheduled_date="2026-12-01T09:00:00Z", timezone="Europe/Madrid").upload_post_publish_video()
    get.assert_not_called()
    data = post.call_args.kwargs["data"]
    assert data["scheduled_date"] == "2026-12-01T09:00:00Z"
    assert data["timezone"] == "Europe/Madrid"
    assert result.data["status"] == "scheduled"
    assert result.data["job_id"] == "a" * 32


def test_api_error_keeps_the_api_message():
    body = {"success": False, "message": "TikTok uploads are not available on the Free plan."}
    with patch(POST_TARGET, MagicMock(return_value=_response(403, json=body))):
        result = _video().upload_post_publish_video()
    assert result.data["error"] == "Upload-Post API error 403: TikTok uploads are not available on the Free plan."


def test_youtube_title_limit_is_checked_before_uploading():
    post = MagicMock()
    with patch(POST_TARGET, post):
        result = _video(title="x" * 101).upload_post_publish_video()
    post.assert_not_called()
    assert "YouTube allows 100" in result.data["error"]


def test_pinterest_requires_a_board():
    post = MagicMock()
    with patch(POST_TARGET, post):
        result = _video(platforms=["pinterest"]).upload_post_publish_video()
    post.assert_not_called()
    assert "Pinterest Board ID" in result.data["error"]


def test_video_needs_a_file_or_url():
    result = _video(video_url="").upload_post_publish_video()
    assert "Video File or a Video URL" in result.data["error"]


def test_video_file_is_sent_as_multipart(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    c = _video(video_url="", video_file=str(video))
    post = MagicMock(return_value=_response(json={}))
    with (
        patch.object(UploadPostVideoComponent, "_local_file", lambda _self, path: path),
        patch(POST_TARGET, post),
        patch(GET_TARGET, MagicMock(return_value=_status_response(COMPLETED))),
    ):
        c.upload_post_publish_video()
    files = post.call_args.kwargs["files"]
    assert [(field, name) for field, (name, _fh) in files] == [("video", "clip.mp4")]
    assert "video" not in post.call_args.kwargs["data"]


def test_photos_urls_become_a_list_field():
    c = UploadPostPhotosComponent()
    for key, value in {
        "upload_post_api_key": "test-key",  # pragma: allowlist secret
        "user": "creator",
        "platforms": ["instagram"],
        "photo_files": [],
        "photo_urls": ["https://example.com/a.jpg", " https://example.com/b.jpg "],
        "title": "Carousel",
        "description": "",
        "tiktok_privacy": "account default",
        "scheduled_date": "",
        "timezone": "",
        "facebook_page_id": "",
        "pinterest_board_id": "",
        "wait_for_result": True,
        "wait_timeout": 300,
    }.items():
        setattr(c, key, value)
    post = MagicMock(return_value=_response(json={}))
    with patch(POST_TARGET, post), patch(GET_TARGET, MagicMock(return_value=_status_response(COMPLETED))):
        c.upload_post_publish_photos()
    assert post.call_args.args[0] == f"{BASE}/api/upload_photos"
    assert post.call_args.kwargs["data"]["photos[]"] == ["https://example.com/a.jpg", "https://example.com/b.jpg"]


def test_text_post_fields():
    c = UploadPostTextComponent()
    for key, value in {
        "upload_post_api_key": "test-key",  # pragma: allowlist secret
        "user": "creator",
        "platforms": ["x", "bluesky"],
        "text": "Hello from Langflow",
        "link_url": "https://langflow.org",
        "scheduled_date": "",
        "timezone": "",
        "facebook_page_id": "",
        "wait_for_result": False,
        "wait_timeout": 300,
    }.items():
        setattr(c, key, value)
    post = MagicMock(return_value=_response(json={}))
    with patch(POST_TARGET, post):
        c.upload_post_publish_text()
    data = post.call_args.kwargs["data"]
    assert post.call_args.args[0] == f"{BASE}/api/upload_text"
    assert data["title"] == "Hello from Langflow"
    assert data["link_url"] == "https://langflow.org"
    assert data["platform[]"] == ["x", "bluesky"]


def test_text_platform_options_exclude_video_only_platforms():
    platforms = next(i for i in UploadPostTextComponent.inputs if i.name == "platforms")
    assert set(platforms.options) == set(_client.TEXT_PLATFORMS)
    assert "tiktok" not in platforms.options


def test_status_asks_job_id_first_for_job_shaped_ids():
    """Scheduled job ids are 32 hex characters; query that kind first."""
    job_id = "b" * 32
    get = MagicMock(return_value=_status_response({"status": "queued", "job_id": job_id, "results": []}))
    c = UploadPostStatusComponent()
    c.upload_post_api_key = "test-key"  # pragma: allowlist secret
    c.upload_id = job_id
    with patch(GET_TARGET, get):
        result = c.upload_post_status()
    assert get.call_count == 1
    assert get.call_args.kwargs["params"] == {"job_id": job_id}
    assert result.data["status"] == "queued"


def test_status_not_found():
    c = UploadPostStatusComponent()
    c.upload_post_api_key = "test-key"  # pragma: allowlist secret
    c.upload_id = "missing-id"
    not_found = _status_response({"status": "not_found"}, status_code=404)
    with patch(GET_TARGET, MagicMock(return_value=not_found)):
        result = c.upload_post_status()
    assert result.data["status"] == "not_found"
    assert result.data["success"] is False
    assert "No Upload-Post upload found" in result.text


def test_tool_mode_exposes_specific_tool_names():
    """Tool names must not collide with other components on the same agent."""
    component = UploadPostVideoComponent(upload_post_api_key="test-key", user="creator")  # pragma: allowlist secret
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == ["upload_post_publish_video"]


def test_scheduled_transport_error_checks_status_instead_of_failing():
    """A dropped connection on a scheduled submit must not be reported as a failure if the job exists."""
    job_id = "c" * 32
    post = MagicMock(side_effect=httpx.ReadTimeout("timed out"))
    get = MagicMock(return_value=_status_response({"status": "queued", "job_id": job_id, "results": []}))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video(scheduled_date="2026-12-01T09:00:00Z").upload_post_publish_video()
    assert post.call_count == 1
    sent_id = post.call_args.kwargs["data"]["request_id"]
    assert get.call_args.kwargs["params"] == {"request_id": sent_id}
    assert result.data["status"] == "scheduled"
    assert result.data["success"] is True
    assert result.data["job_id"] == job_id


def test_scheduled_transport_error_not_found_keeps_request_id():
    post = MagicMock(side_effect=httpx.ConnectError("refused"))
    not_found = _status_response({"status": "not_found"}, status_code=404)
    with patch(POST_TARGET, post), patch(GET_TARGET, MagicMock(return_value=not_found)):
        result = _video(scheduled_date="2026-12-01T09:00:00Z").upload_post_publish_video()
    assert result.data["success"] is False
    assert result.data["status"] == "not_found"
    assert result.data["request_id"] == post.call_args.kwargs["data"]["request_id"]


def test_status_check_failure_after_accepted_upload_keeps_request_id():
    """submit() succeeded but wait() failed: the result must carry the request_id and a submitted state."""
    post = MagicMock(return_value=_response(json={"success": True}))
    get = MagicMock(side_effect=httpx.ConnectError("status down"))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video().upload_post_publish_video()
    assert result.data["request_id"] == post.call_args.kwargs["data"]["request_id"]
    assert result.data["status"] == "submitted"
    assert result.data["success"] is True
    assert "status down" in result.data["error"]


def test_status_check_failure_after_transport_error_is_unknown():
    post = MagicMock(side_effect=httpx.ReadTimeout("timed out"))
    get = MagicMock(side_effect=httpx.ConnectError("status down"))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video().upload_post_publish_video()
    assert result.data["status"] == "unknown"
    assert result.data["success"] is False
    assert result.data["request_id"] == post.call_args.kwargs["data"]["request_id"]


def test_non_json_2xx_submit_is_an_accepted_submission():
    """An empty or non-JSON 2xx body means the upload was accepted, not failed."""
    post = MagicMock(return_value=_response(200, content=b""))
    with patch(POST_TARGET, post), patch(GET_TARGET, MagicMock()):
        result = _video(wait_for_result=False).upload_post_publish_video()
    assert result.data["status"] == "submitted"
    assert result.data["success"] is True
    assert result.data["request_id"] == post.call_args.kwargs["data"]["request_id"]


def _server_error(code: int = 503):
    return _response(code, json={"success": False, "message": "Service Unavailable"})


def test_immediate_5xx_is_ambiguous_and_checks_the_request_id():
    """A 503 on submit may still have stored the upload: check it, never re-send."""
    post = MagicMock(return_value=_server_error(503))
    get = MagicMock(return_value=_status_response(COMPLETED))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video(wait_for_result=False).upload_post_publish_video()
    assert post.call_count == 1
    assert get.call_args.kwargs["params"] == {"request_id": post.call_args.kwargs["data"]["request_id"]}
    assert result.data["status"] == "completed"
    assert result.data["success"] is True


def test_scheduled_5xx_is_ambiguous_and_reports_the_existing_job():
    job_id = "d" * 32
    post = MagicMock(return_value=_server_error(503))
    get = MagicMock(return_value=_status_response({"status": "queued", "job_id": job_id, "results": []}))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video(scheduled_date="2026-12-01T09:00:00Z").upload_post_publish_video()
    assert post.call_count == 1
    assert result.data["status"] == "scheduled"
    assert result.data["success"] is True
    assert result.data["job_id"] == job_id


def test_5xx_with_unreachable_status_is_unknown_with_request_id():
    post = MagicMock(return_value=_server_error(502))
    get = MagicMock(side_effect=httpx.ConnectError("status down"))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video().upload_post_publish_video()
    assert result.data["status"] == "unknown"
    assert result.data["success"] is False
    assert result.data["request_id"] == post.call_args.kwargs["data"]["request_id"]


def test_5xx_then_not_found_keeps_request_id():
    post = MagicMock(return_value=_server_error(500))
    not_found = _status_response({"status": "not_found"}, status_code=404)
    with patch(POST_TARGET, post), patch(GET_TARGET, MagicMock(return_value=not_found)):
        result = _video().upload_post_publish_video()
    assert result.data["status"] == "not_found"
    assert result.data["success"] is False
    assert result.data["request_id"] == post.call_args.kwargs["data"]["request_id"]


@pytest.mark.parametrize("code", [400, 401, 403, 422])
def test_4xx_is_a_definitive_rejection_without_status_check(code):
    get = MagicMock()
    post = MagicMock(return_value=_response(code, json={"success": False, "message": "rejected"}))
    with patch(POST_TARGET, post), patch(GET_TARGET, get):
        result = _video().upload_post_publish_video()
    get.assert_not_called()
    assert result.data["success"] is False
    assert result.data["error"] == f"Upload-Post API error {code}: rejected"
