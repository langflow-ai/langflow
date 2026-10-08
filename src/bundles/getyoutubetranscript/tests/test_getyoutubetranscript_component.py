"""Unit tests for the GetYouTubeTranscript extension bundle (``lfx-getyoutubetranscript``).

The component calls the GetYouTubeTranscript API with ``httpx``; the tests patch
``httpx.get`` at the component module to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_getyoutubetranscript import GetYouTubeTranscriptComponent

GET_PATCH_TARGET = "lfx_getyoutubetranscript.components.getyoutubetranscript.getyoutubetranscript.httpx.get"
TRANSCRIPT_URL = "https://getyoutubetranscript.com/api/v1/transcript"

PLAIN_DATA = {
    "video_id": "abc12345678",
    "language_code": "en",
    "title": "A video",
    "author_name": "A channel",
    "transcript": "hello world this is a test",
    "word_count": 6,
}

SEGMENT_DATA = {
    **PLAIN_DATA,
    "segments": [
        {"start": 0.0, "duration": 2.5, "text": "hello world"},
        {"start": 65.2, "duration": 3.0, "text": "this is a test"},
        {"start": 3725.0, "duration": 1.0, "text": "an hour in"},
    ],
}


def _response(status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", TRANSCRIPT_URL), **kwargs)


def _mock_get(data: object) -> MagicMock:
    return MagicMock(return_value=_response(json={"success": True, "data": data}))


@pytest.fixture
def component() -> GetYouTubeTranscriptComponent:
    c = GetYouTubeTranscriptComponent()
    c.video = "https://youtu.be/abc12345678"
    c.getyoutubetranscript_api_key = "test-key"  # pragma: allowlist secret
    c.language = ""
    c.include_timestamps = False
    return c


def test_component_metadata():
    """Class name must stay stable for saved flows."""
    assert GetYouTubeTranscriptComponent.__name__ == "GetYouTubeTranscriptComponent"


def test_missing_api_key_raises(component):
    """No key set -> clear ValueError instead of an anonymous request."""
    component.getyoutubetranscript_api_key = ""
    with pytest.raises(ValueError, match="API key is required"):
        component._fetch()


def test_missing_video_raises(component):
    """An empty video input is rejected before any request is made."""
    component.video = "  "
    mock_get = _mock_get(PLAIN_DATA)
    with patch(GET_PATCH_TARGET, mock_get), pytest.raises(ValueError, match="video URL or ID is required"):
        component._fetch()
    mock_get.assert_not_called()


def test_output_reports_missing_api_key_without_request(component):
    """The public outputs turn a missing key into an error and never call the API."""
    component.getyoutubetranscript_api_key = ""
    mock_get = _mock_get(PLAIN_DATA)
    with patch(GET_PATCH_TARGET, mock_get):
        message = component.get_youtube_transcript()
        data = component.get_transcript_data()
    mock_get.assert_not_called()
    assert "API key is required" in message.text
    assert "API key is required" in data.data["error"]


def test_fetch_sends_bearer_header_and_video_param(component):
    """The request is a GET to the transcript endpoint with the key as a Bearer token."""
    mock_get = _mock_get(PLAIN_DATA)
    with patch(GET_PATCH_TARGET, mock_get):
        component._fetch()
    assert mock_get.call_args.args[0] == TRANSCRIPT_URL
    headers = mock_get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"  # pragma: allowlist secret
    assert headers["User-Agent"] == "langflow-getyoutubetranscript-bundle"
    assert mock_get.call_args.kwargs["params"] == {"v": "https://youtu.be/abc12345678"}


def test_fetch_sends_language_and_timestamps_only_when_set(component):
    """Language and timestamps are sent only when set."""
    component.language = " es "
    component.include_timestamps = True
    mock_get = _mock_get(SEGMENT_DATA)
    with patch(GET_PATCH_TARGET, mock_get):
        component._fetch()
    assert mock_get.call_args.kwargs["params"] == {
        "v": "https://youtu.be/abc12345678",
        "language": "es",
        "timestamps": "true",
    }


def test_transcript_message_is_plain_text(component):
    """Without timestamps the Message is the API's transcript string."""
    with patch(GET_PATCH_TARGET, _mock_get(PLAIN_DATA)):
        message = component.get_youtube_transcript()
    assert message.text == "hello world this is a test"


def test_transcript_message_with_timestamps(component):
    """With timestamps each segment becomes a line prefixed with its start time."""
    component.include_timestamps = True
    with patch(GET_PATCH_TARGET, _mock_get(SEGMENT_DATA)):
        message = component.get_youtube_transcript()
    assert message.text.splitlines() == [
        "[00:00] hello world",
        "[01:05] this is a test",
        "[1:02:05] an hour in",
    ]


def test_timestamps_fall_back_to_plain_text_without_segments(component):
    """If the API returns no segments, the plain transcript is used."""
    component.include_timestamps = True
    with patch(GET_PATCH_TARGET, _mock_get(PLAIN_DATA)):
        message = component.get_youtube_transcript()
    assert message.text == "hello world this is a test"


def test_transcript_data_carries_metadata_and_segments(component):
    """The Data output keeps the video metadata and the segments list."""
    component.include_timestamps = True
    with patch(GET_PATCH_TARGET, _mock_get(SEGMENT_DATA)):
        result = component.get_transcript_data()
    assert result.data["title"] == "A video"
    assert result.data["author_name"] == "A channel"
    assert result.data["language_code"] == "en"
    assert result.data["word_count"] == 6
    assert len(result.data["segments"]) == 3
    assert "error" not in result.data


def test_surfaces_api_error_message(component):
    """A 401 keeps the API's own message instead of the generic httpx message."""
    body = {"success": False, "code": "INVALID_API_KEY", "message": "The API key is wrong or revoked."}
    mock_get = MagicMock(return_value=_response(401, json=body))
    with patch(GET_PATCH_TARGET, mock_get):
        message = component.get_youtube_transcript()
        data = component.get_transcript_data()
    expected = "GetYouTubeTranscript API error 401: The API key is wrong or revoked."
    assert message.text == expected
    assert data.data["error"] == expected


def test_http_error_without_json_body(component):
    """A non-JSON error body is kept as a whitespace-normalized excerpt."""
    mock_get = MagicMock(return_value=_response(502, text="upstream\n   down"))
    with patch(GET_PATCH_TARGET, mock_get):
        message = component.get_youtube_transcript()
    assert message.text == "GetYouTubeTranscript API error 502: upstream down"


def test_http_error_body_excerpt_is_capped(component):
    """A long non-JSON body is cut to 200 characters."""
    mock_get = MagicMock(return_value=_response(502, text="x" * 500))
    with patch(GET_PATCH_TARGET, mock_get):
        message = component.get_youtube_transcript()
    assert message.text == "GetYouTubeTranscript API error 502: " + "x" * 200


def test_http_error_with_empty_body_uses_reason_phrase(component):
    """An empty error body falls back to the HTTP reason phrase."""
    mock_get = MagicMock(return_value=_response(502, text=""))
    with patch(GET_PATCH_TARGET, mock_get):
        message = component.get_youtube_transcript()
    assert message.text == "GetYouTubeTranscript API error 502: Bad Gateway"


def test_both_outputs_share_one_request_per_build(component):
    """Building both outputs makes a single API call, so only one credit is spent."""
    component._pre_run_setup()
    mock_get = _mock_get(PLAIN_DATA)
    with patch(GET_PATCH_TARGET, mock_get):
        message = component.get_youtube_transcript()
        data = component.get_transcript_data()
    assert mock_get.call_count == 1
    assert message.text == data.text == "hello world this is a test"


def test_changed_inputs_fetch_again_without_a_new_build(component):
    """The shared result is keyed by the inputs, so a different video is never served stale.

    Tool calls copy the component and set new inputs without a new build, so this must hold
    even when ``_pre_run_setup`` is not called in between.
    """
    mock_get = _mock_get(PLAIN_DATA)
    with patch(GET_PATCH_TARGET, mock_get):
        component.get_youtube_transcript()
        component.video = "otherVideo1"
        component.get_youtube_transcript()
        component.include_timestamps = True
        component.get_youtube_transcript()
    assert mock_get.call_count == 3
    assert mock_get.call_args.kwargs["params"]["v"] == "otherVideo1"


def test_next_build_fetches_again(component):
    """Each build starts fresh, so a rerun with the same inputs makes a new request."""
    mock_get = _mock_get(PLAIN_DATA)
    with patch(GET_PATCH_TARGET, mock_get):
        component._pre_run_setup()
        component.get_youtube_transcript()
        component._pre_run_setup()
        component.get_youtube_transcript()
    assert mock_get.call_count == 2


def test_transport_error_becomes_error_output(component):
    """A transport error is surfaced as an error output, not raised."""
    mock_get = MagicMock(side_effect=httpx.ConnectError("boom"))
    with patch(GET_PATCH_TARGET, mock_get):
        message = component.get_youtube_transcript()
        data = component.get_transcript_data()
    assert "boom" in message.text
    assert "boom" in data.data["error"]


@pytest.mark.parametrize("payload", [["unexpected"], {"success": True}, {"success": True, "data": "text"}])
def test_unexpected_payload_becomes_error_output(component, payload):
    """A body without a data object becomes an error output, not an AttributeError."""
    mock_get = MagicMock(return_value=_response(json=payload))
    with patch(GET_PATCH_TARGET, mock_get):
        message = component.get_youtube_transcript()
    assert "unexpected response" in message.text


def test_tool_mode_exposes_a_single_specific_tool():
    """Only the text output is a tool, and its name must not collide with other YouTube components."""
    # Tools read inputs the way a graph sets them (constructor kwargs), not
    # attributes assigned after construction, so build the component directly.
    component = GetYouTubeTranscriptComponent(
        getyoutubetranscript_api_key="test-key",  # pragma: allowlist secret
        include_timestamps=False,
    )
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == ["get_youtube_transcript"]

    mock_get = _mock_get(PLAIN_DATA)
    with patch(GET_PATCH_TARGET, mock_get):
        output = asyncio.run(tools[0].ainvoke({"video": "abc12345678"}))
    assert mock_get.call_args.kwargs["params"] == {"v": "abc12345678"}
    assert "hello world" in str(output)
