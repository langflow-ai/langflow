"""Unit tests for the SocialScrape components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.get``, so the tests exercise the real
paths, headers, query parameters and error handling of the client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.socialscrape.socialscrape_common import API_BASE_URL
from lfx_bundles.socialscrape.socialscrape_posts import SocialScrapePostsComponent
from lfx_bundles.socialscrape.socialscrape_profile import SocialScrapeProfileComponent
from lfx_bundles.socialscrape.socialscrape_transcript import SocialScrapeTranscriptComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "ss_live_test_placeholder_key"  # pragma: allowlist secret

ALL_COMPONENTS = [SocialScrapeTranscriptComponent, SocialScrapeProfileComponent, SocialScrapePostsComponent]

TRANSCRIPT = {
    "platform": "youtube",
    "video_id": "abc123",
    "url": "https://www.youtube.com/watch?v=abc123",
    "language": "en",
    "source": "captions",
    "duration_seconds": 12,
    "text": "Hello world. This is a test.",
    "segments": [{"start": 0.0, "end": 2.0, "text": "Hello world."}],
    "available_languages": ["en"],
}
PROFILE = {
    "platform": "instagram",
    "id": "1",
    "handle": "nasa",
    "name": "NASA",
    "bio": "Explore the universe.",
    "stats": {"followers": 100, "following": 1, "posts": 5},
}
JOB = {
    "object": "job",
    "job_id": "job_0123456789abcdef01234567",
    "status": "running",
    "poll_url": "https://api.socialscrape.dev/v1/jobs/job_0123456789abcdef01234567",
}
POSTS_PAGE = {
    "items": [
        {"platform": "instagram", "id": "p1", "url": "https://x/p1", "type": "image", "text": "First post"},
        {"platform": "instagram", "id": "p2", "url": "https://x/p2", "type": "video", "text": None},
    ],
    "cursor": "next-page-token",
    "has_more": True,
}


def _response(status_code: int = 200, *, data: Any = None, json_body: Any = None, text: str | None = None):
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    if json_body is None:
        json_body = {"ok": True, "credits_charged": 1, "credits_remaining": 9, "cached": False, "data": data}
    return httpx.Response(status_code, json=json_body, request=request)


def _error(status_code: int, code: str, message: str):
    body = {"ok": False, "error": {"code": code, "message": message, "retryable": False}, "credits_charged": 0}
    return _response(status_code, json_body=body)


def _transcript(**values) -> SocialScrapeTranscriptComponent:
    component = SocialScrapeTranscriptComponent()
    component.set(**{"api_key": API_KEY, "url": TRANSCRIPT["url"], **values})
    return component


def _profile(**values) -> SocialScrapeProfileComponent:
    component = SocialScrapeProfileComponent()
    component.set(**{"api_key": API_KEY, "platform": "instagram", "handle": "nasa", **values})
    return component


def _posts(**values) -> SocialScrapePostsComponent:
    component = SocialScrapePostsComponent()
    component.set(**{"api_key": API_KEY, "platform": "instagram", "handle": "nasa", **values})
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
class TestMetadata:
    def test_inputs_do_not_shadow_component_attributes(self, component_class) -> None:
        shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
        assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"

    def test_metadata_and_required_key(self, component_class) -> None:
        component = component_class()
        assert component.icon == "Share2"
        assert "socialscrape.dev" in component.documentation
        api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
        assert api_key.required is True


@pytest.mark.unit
class TestTranscript:
    def test_returns_text_and_data_and_sends_key_header(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data=TRANSCRIPT)) as get:
            result = _transcript().get_transcript()

        assert get.call_args.args[0] == f"{API_BASE_URL}/v1/transcript"
        assert get.call_args.kwargs["params"] == {"url": TRANSCRIPT["url"]}
        assert get.call_args.kwargs["headers"]["x-api-key"] == API_KEY
        assert result.text == TRANSCRIPT["text"]
        assert result.data["video_id"] == "abc123"
        assert result.data["segments"][0]["text"] == "Hello world."

    def test_language_is_sent_only_when_set(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data=TRANSCRIPT)) as get:
            _transcript(language=" es ").get_transcript()

        assert get.call_args.kwargs["params"] == {"url": TRANSCRIPT["url"], "language": "es"}

    def test_long_transcription_is_never_requested(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data=TRANSCRIPT)) as get:
            _transcript().get_transcript()

        assert "allow_long_transcription" not in get.call_args.kwargs["params"]

    def test_default_timeout_allows_for_audio_transcription(self) -> None:
        with (
            patch("httpx.Client.get", return_value=_response(data=TRANSCRIPT)),
            patch("httpx.Client", wraps=httpx.Client) as client,
        ):
            _transcript().get_transcript()

        assert client.call_args.kwargs["timeout"] >= 60

    def test_queued_job_is_polled_until_the_transcript_is_ready(self) -> None:
        answers = [_response(202, data=JOB), _response(202, data=JOB), _response(data=TRANSCRIPT)]
        with patch("httpx.Client.get", side_effect=answers) as get, patch("time.sleep") as sleep:
            result = _transcript().get_transcript()

        assert result.text == TRANSCRIPT["text"]
        assert [call.args[0] for call in get.call_args_list[1:]] == [f"{API_BASE_URL}/v1/jobs/{JOB['job_id']}"] * 2
        assert sleep.call_count == 2

    def test_job_still_running_after_the_wait_is_an_error_naming_the_job(self) -> None:
        with (
            patch("httpx.Client.get", return_value=_response(202, data=JOB)),
            patch("time.sleep"),
            patch("time.monotonic", side_effect=range(0, 100_000, 40)),
        ):
            result = _transcript().get_transcript()

        assert JOB["job_id"] in result.data["error"]

    def test_job_without_a_usable_id_is_refused_without_polling(self) -> None:
        bad = {"object": "job", "job_id": "../account/credits", "status": "queued"}
        with patch("httpx.Client.get", return_value=_response(202, data=bad)) as get, patch("time.sleep"):
            result = _transcript().get_transcript()

        assert "without a usable job id" in result.data["error"]
        assert get.call_count == 1

    @pytest.mark.parametrize("url", ["", "youtube.com/watch?v=1", "file:///etc/passwd", "https://[example"])
    def test_rejects_non_http_urls_without_a_request(self, url: str) -> None:
        with patch("httpx.Client.get") as get:
            result = _transcript(url=url).get_transcript()

        get.assert_not_called()
        assert "absolute http(s) video URL" in result.data["error"]

    def test_missing_key_makes_no_request(self) -> None:
        with patch("httpx.Client.get") as get:
            result = _transcript(api_key="").get_transcript()

        get.assert_not_called()
        assert "Enter a SocialScrape API key" in result.data["error"]

    def test_api_error_message_is_returned(self) -> None:
        with patch("httpx.Client.get", return_value=_error(404, "not_found", "No transcript for this video")):
            result = _transcript().get_transcript()

        assert result.data["error"] == "SocialScrape API error (404): No transcript for this video"

    def test_out_of_credits_and_rate_limit_have_clear_labels(self) -> None:
        with patch("httpx.Client.get", return_value=_error(402, "insufficient_credits", "Top up")):
            assert "out of credits (402)" in _transcript().get_transcript().data["error"]
        with patch("httpx.Client.get", return_value=_error(429, "rate_limited", "Slow down")):
            assert "rate limit exceeded (429)" in _transcript().get_transcript().data["error"]

    def test_key_is_redacted_from_error_text_even_when_cut_at_the_limit(self) -> None:
        with patch("httpx.Client.get", return_value=_error(500, "boom", "x" * 290 + API_KEY)):
            result = _transcript().get_transcript()

        assert API_KEY[:10] not in result.data["error"]

    def test_non_json_and_missing_data_are_errors(self) -> None:
        with patch("httpx.Client.get", return_value=_response(text="<html>bad gateway</html>")):
            assert "not JSON" in _transcript().get_transcript().data["error"]
        with patch("httpx.Client.get", return_value=_response(json_body={"ok": True})):
            assert "without a data object" in _transcript().get_transcript().data["error"]

    def test_timeout_and_connection_errors(self) -> None:
        with patch("httpx.Client.get", side_effect=httpx.ReadTimeout("slow")):
            result = _transcript(timeout=2.5).get_transcript()
        assert result.data["error"] == "SocialScrape request timed out after 2.5 seconds."
        with patch("httpx.Client.get", side_effect=httpx.ConnectError("connection refused")):
            result = _transcript().get_transcript()
        assert result.data["error"].startswith("Could not reach the SocialScrape API: ConnectError")


@pytest.mark.unit
class TestProfile:
    def test_returns_profile_with_bio_as_text(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data=PROFILE)) as get:
            result = _profile().get_profile()

        assert get.call_args.args[0] == f"{API_BASE_URL}/v1/instagram/profile"
        assert get.call_args.kwargs["params"] == {"handle": "nasa"}
        assert result.text == "Explore the universe."
        assert result.data["stats"]["followers"] == 100

    def test_slow_lookup_is_polled_and_never_returned_as_a_job(self) -> None:
        with (
            patch("httpx.Client.get", side_effect=[_response(202, data=JOB), _response(data=PROFILE)]),
            patch("time.sleep"),
        ):
            result = _profile().get_profile()

        assert result.data["handle"] == "nasa"
        assert "job_id" not in result.data

    def test_leading_at_sign_is_removed(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data=PROFILE)) as get:
            _profile(handle="  @nasa ", platform="twitter").get_profile()

        assert get.call_args.args[0] == f"{API_BASE_URL}/v1/twitter/profile"
        assert get.call_args.kwargs["params"] == {"handle": "nasa"}

    @pytest.mark.parametrize("handle", ["", "  ", "@"])
    def test_empty_handle_makes_no_request(self, handle: str) -> None:
        with patch("httpx.Client.get") as get:
            result = _profile(handle=handle).get_profile()

        get.assert_not_called()
        assert "Enter a profile handle" in result.data["error"]

    def test_unknown_platform_makes_no_request(self) -> None:
        with patch("httpx.Client.get") as get:
            result = _profile(platform="../account/credits").get_profile()

        get.assert_not_called()
        assert "Choose a platform" in result.data["error"]

    def test_api_error_is_returned(self) -> None:
        with patch("httpx.Client.get", return_value=_error(401, "unauthorized", "Invalid API key")):
            result = _profile().get_profile()

        assert result.data["error"] == "SocialScrape rejected the API key (401): Invalid API key"


@pytest.mark.unit
class TestPosts:
    def test_returns_one_row_per_post(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data=POSTS_PAGE)) as get:
            frame = _posts().get_posts()

        assert get.call_args.args[0] == f"{API_BASE_URL}/v1/instagram/profile/posts"
        assert get.call_args.kwargs["params"] == {"handle": "nasa"}
        assert list(frame["id"]) == ["p1", "p2"]
        assert list(frame["text"]) == ["First post", None]

    def test_tiktok_uses_the_videos_route(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data=POSTS_PAGE)) as get:
            _posts(platform="tiktok").get_posts()

        assert get.call_args.args[0] == f"{API_BASE_URL}/v1/tiktok/profile/videos"

    def test_cursor_is_sent_when_set(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data=POSTS_PAGE)) as get:
            _posts(cursor="abc").get_posts()

        assert get.call_args.kwargs["params"] == {"handle": "nasa", "cursor": "abc"}

    def test_page_info_has_cursor_and_has_more(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data=POSTS_PAGE)):
            info = _posts().get_page_info()

        assert info.data == {"cursor": "next-page-token", "has_more": True}

    def test_both_outputs_share_one_request(self) -> None:
        component = _posts()
        with patch("httpx.Client.get", return_value=_response(data=POSTS_PAGE)) as get:
            component.get_posts()
            component.get_page_info()

        assert get.call_count == 1

    def test_changed_inputs_fetch_again(self) -> None:
        component = _posts()
        with patch("httpx.Client.get", return_value=_response(data=POSTS_PAGE)) as get:
            component.get_posts()
            component.set(cursor="next-page-token")
            component.get_posts()
            component.get_page_info()

        assert get.call_count == 2
        assert get.call_args.kwargs["params"]["cursor"] == "next-page-token"

    def test_answer_without_items_is_an_error(self) -> None:
        with patch("httpx.Client.get", return_value=_response(data={"cursor": None})):
            frame = _posts().get_posts()

        assert "without a list of items" in frame.iloc[0]["error"]

    def test_unsupported_platform_makes_no_request(self) -> None:
        with patch("httpx.Client.get") as get:
            frame = _posts(platform="twitter").get_posts()

        get.assert_not_called()
        assert "Choose a platform" in frame.iloc[0]["error"]
