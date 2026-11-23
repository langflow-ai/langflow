"""Unit tests for the WaveSpeed components with mocked HTTP calls.

Requests are intercepted at ``httpx.AsyncClient.post`` and ``httpx.AsyncClient.get``,
so the tests exercise the real URLs, headers, request bodies, polling and error
handling of the client without network access.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.wavespeed import wavespeed_common
from lfx_bundles.wavespeed.wavespeed_common import API_BASE_URL
from lfx_bundles.wavespeed.wavespeed_image_generation import WaveSpeedImageGenerationComponent
from lfx_bundles.wavespeed.wavespeed_video_generation import WaveSpeedVideoGenerationComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "ws_test_placeholder_key"  # pragma: allowlist secret
PREDICTION_ID = "0123456789abcdef"
RESULT_URL = f"{API_BASE_URL}/predictions/{PREDICTION_ID}/result"
IMAGE_OUT = "https://cdn.example.com/out.png"
VIDEO_OUT = "https://cdn.example.com/out.mp4"
ALL_COMPONENTS = [WaveSpeedImageGenerationComponent, WaveSpeedVideoGenerationComponent]


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _envelope(data: Any, code: int = 200, message: str = "success") -> httpx.Response:
    return _response(json_body={"code": code, "message": message, "data": data})


def _submitted() -> httpx.Response:
    return _envelope({"id": PREDICTION_ID, "status": "created", "outputs": []})


def _status(status: str, outputs: list[str] | None = None, error: str = "") -> httpx.Response:
    return _envelope({"id": PREDICTION_ID, "status": status, "outputs": outputs or [], "error": error})


@pytest.fixture(autouse=True)
def no_poll_delay(monkeypatch):
    monkeypatch.setattr(wavespeed_common, "POLL_INTERVAL_SECONDS", 0)


def _image(**values) -> WaveSpeedImageGenerationComponent:
    component = WaveSpeedImageGenerationComponent()
    component.set(**{"api_key": API_KEY, "prompt": "a red fox in snow", **values})
    return component


def _video(**values) -> WaveSpeedVideoGenerationComponent:
    component = WaveSpeedVideoGenerationComponent()
    component.set(**{"api_key": API_KEY, "prompt": "waves at sunset", **values})
    return component


def _mock_http(post: Any, gets: list[Any]):
    """Patch the client: ``post`` is one response or exception; ``gets`` are returned in order."""
    post_mock = AsyncMock(side_effect=[post])
    get_mock = AsyncMock(side_effect=gets)
    return (
        patch("httpx.AsyncClient.post", post_mock),
        patch("httpx.AsyncClient.get", get_mock),
        post_mock,
        get_mock,
    )


async def _run_image(component, post, gets):
    post_patch, get_patch, post_mock, get_mock = _mock_http(post, gets)
    with post_patch, get_patch:
        result = await component.generate_image()
    return result, post_mock, get_mock


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
class TestMetadata:
    def test_inputs_do_not_shadow_component_attributes(self, component_class) -> None:
        shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
        assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"

    def test_api_key_is_required_and_defaults_to_the_environment_variable(self, component_class) -> None:
        api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
        assert api_key.required is True
        assert api_key.value == "WAVESPEED_API_KEY"
        assert "wavespeed.ai" in component_class.documentation


@pytest.mark.unit
class TestImageGeneration:
    async def test_text_to_image_submits_once_and_polls_until_completed(self) -> None:
        result, post, get = await _run_image(
            _image(), _submitted(), [_status("processing"), _status("completed", [IMAGE_OUT])]
        )

        post.assert_awaited_once()
        assert post.call_args.args[0] == f"{API_BASE_URL}/bytedance/seedream-v5.5"
        assert post.call_args.kwargs["json"] == {"prompt": "a red fox in snow"}
        assert post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {API_KEY}"
        assert get.await_count == 2
        assert get.call_args.args[0] == RESULT_URL
        assert result.text == IMAGE_OUT
        assert result.data["image_url"] == IMAGE_OUT
        assert result.data["image_urls"] == [IMAGE_OUT]
        assert result.data["model"] == "bytedance/seedream-v5.5"
        assert result.data["prediction_id"] == PREDICTION_ID

    async def test_aspect_ratio_and_resolution_are_sent_when_chosen(self) -> None:
        _result, post, _get = await _run_image(
            _image(aspect_ratio="16:9", resolution="1k"), _submitted(), [_status("completed", [IMAGE_OUT])]
        )
        assert post.call_args.kwargs["json"] == {
            "prompt": "a red fox in snow",
            "aspect_ratio": "16:9",
            "resolution": "1k",
        }

    async def test_image_urls_switch_the_default_model_to_edit(self) -> None:
        urls = ["https://example.com/a.png", " https://example.com/b.png "]
        result, post, _get = await _run_image(
            _image(image_urls=urls), _submitted(), [_status("completed", [IMAGE_OUT])]
        )
        assert post.call_args.args[0] == f"{API_BASE_URL}/bytedance/seedream-v5.5/edit"
        assert post.call_args.kwargs["json"]["images"] == ["https://example.com/a.png", "https://example.com/b.png"]
        assert result.data["model"] == "bytedance/seedream-v5.5/edit"

    async def test_blank_image_urls_are_ignored(self) -> None:
        _result, post, _get = await _run_image(
            _image(image_urls=["", "  "]), _submitted(), [_status("completed", [IMAGE_OUT])]
        )
        assert post.call_args.args[0] == f"{API_BASE_URL}/bytedance/seedream-v5.5"
        assert "images" not in post.call_args.kwargs["json"]

    async def test_custom_model_is_kept_and_extra_input_is_merged(self) -> None:
        component = _image(
            model=" vendor/some-image-model/edit ",
            image_urls=["https://example.com/a.png"],
            extra_input='{"output_format": "jpeg", "seed": 7}',
        )
        _result, post, _get = await _run_image(component, _submitted(), [_status("completed", [IMAGE_OUT])])
        assert post.call_args.args[0] == f"{API_BASE_URL}/vendor/some-image-model/edit"
        assert post.call_args.kwargs["json"] == {
            "prompt": "a red fox in snow",
            "images": ["https://example.com/a.png"],
            "output_format": "jpeg",
            "seed": 7,
        }

    @pytest.mark.parametrize(
        ("values", "message"),
        [
            ({"api_key": ""}, "Enter a WaveSpeed API key"),
            ({"prompt": "   "}, "Enter a prompt"),
            ({"model": "../admin"}, "Enter a WaveSpeed model id"),
            ({"model": "seedream"}, "Enter a WaveSpeed model id"),
            ({"image_urls": ["file:///etc/passwd"]}, "absolute http"),
            ({"image_urls": [f"https://example.com/{i}.png" for i in range(11)]}, "up to 10 images"),
            ({"extra_input": "[1, 2]"}, "JSON object"),
            ({"extra_input": "{not json"}, "JSON object"),
        ],
    )
    async def test_invalid_input_is_reported_without_a_request(self, values, message) -> None:
        result, post, get = await _run_image(_image(**values), _submitted(), [])
        post.assert_not_awaited()
        get.assert_not_awaited()
        assert message in result.data["error"]
        assert result.text == result.data["error"]

    async def test_envelope_error_code_on_submit_is_an_error(self) -> None:
        result, post, get = await _run_image(_image(), _envelope(None, code=400, message="prompt is required"), [])
        post.assert_awaited_once()
        get.assert_not_awaited()
        assert result.data["error"] == "WaveSpeed API error (400): prompt is required"

    async def test_http_error_is_reported_without_leaking_the_key(self) -> None:
        body = {"code": 401, "message": f"invalid token {API_KEY}"}
        result, _post, get = await _run_image(_image(), _response(401, json_body=body), [])
        get.assert_not_awaited()
        assert result.data["error"] == "WaveSpeed API error (401): invalid token ***"
        assert API_KEY not in result.text

    async def test_submit_without_prediction_id_is_an_error(self) -> None:
        result, _post, get = await _run_image(_image(), _envelope({"status": "created"}), [])
        get.assert_not_awaited()
        assert "no usable prediction id" in result.data["error"]

    async def test_submit_timeout_is_not_retried(self) -> None:
        result, post, get = await _run_image(_image(), httpx.ReadTimeout("slow"), [])
        post.assert_awaited_once()
        get.assert_not_awaited()
        assert "may still have been accepted" in result.data["error"]

    @pytest.mark.parametrize("status", ["failed", "cancelled", "timeout"])
    async def test_final_failure_status_is_an_error(self, status) -> None:
        result, post, _get = await _run_image(
            _image(), _submitted(), [_status("processing"), _status(status, error="content flagged")]
        )
        post.assert_awaited_once()
        assert result.data["error"] == f"WaveSpeed run {PREDICTION_ID} {status}: content flagged"

    async def test_completed_without_outputs_is_an_error(self) -> None:
        result, _post, _get = await _run_image(_image(), _submitted(), [_status("completed", [])])
        assert "completed without any output" in result.data["error"]

    async def test_envelope_error_code_while_polling_is_an_error(self) -> None:
        result, _post, _get = await _run_image(
            _image(), _submitted(), [_envelope(None, code=404, message="prediction not found")]
        )
        assert result.data["error"] == "WaveSpeed API error (404): prediction not found"

    async def test_transient_poll_errors_are_retried_without_resubmitting(self) -> None:
        gets = [httpx.ConnectError("reset"), _response(503, text="busy"), _status("completed", [IMAGE_OUT])]
        result, post, get = await _run_image(_image(), _submitted(), gets)
        post.assert_awaited_once()
        assert get.await_count == 3
        assert result.data["image_url"] == IMAGE_OUT

    async def test_run_still_going_after_the_timeout_is_an_error(self, monkeypatch) -> None:
        monkeypatch.setattr(wavespeed_common, "POLL_INTERVAL_SECONDS", 0.01)
        post_patch, _unused, post, _unused_get = _mock_http(_submitted(), [])
        get = AsyncMock(return_value=_status("processing"))
        with post_patch, patch("httpx.AsyncClient.get", get):
            result = await _image(timeout=0.05).generate_image()
        post.assert_awaited_once()
        assert result.data["error"] == f"WaveSpeed run {PREDICTION_ID} did not finish within 0.05 seconds."


@pytest.mark.unit
class TestVideoGeneration:
    async def _run(self, component, gets):
        post_patch, get_patch, post_mock, _get_mock = _mock_http(_submitted(), gets)
        with post_patch, get_patch:
            result = await component.generate_video()
        return result, post_mock

    async def test_text_to_video_sends_the_default_duration(self) -> None:
        result, post = await self._run(_video(), [_status("completed", [VIDEO_OUT])])
        assert post.call_args.args[0] == f"{API_BASE_URL}/alibaba/wan-3.0/text-to-video"
        assert post.call_args.kwargs["json"] == {"prompt": "waves at sunset", "duration": 5}
        assert result.data["video_url"] == VIDEO_OUT
        assert result.data["video_urls"] == [VIDEO_OUT]
        assert result.data["prediction_id"] == PREDICTION_ID

    async def test_image_url_switches_the_default_model_to_image_to_video(self) -> None:
        component = _video(
            image_url="https://example.com/first.png", resolution="720p", aspect_ratio="9:16", duration=0
        )
        result, post = await self._run(component, [_status("completed", [VIDEO_OUT])])
        assert post.call_args.args[0] == f"{API_BASE_URL}/alibaba/wan-3.0/image-to-video"
        assert post.call_args.kwargs["json"] == {
            "prompt": "waves at sunset",
            "image": "https://example.com/first.png",
            "aspect_ratio": "9:16",
            "resolution": "720p",
        }
        assert result.data["model"] == "alibaba/wan-3.0/image-to-video"

    async def test_invalid_image_url_is_reported_without_a_request(self) -> None:
        result, post = await self._run(_video(image_url="not a url"), [])
        post.assert_not_awaited()
        assert "Image URL must be an absolute http(s) URL" in result.data["error"]

    async def test_failed_run_is_an_error(self) -> None:
        result, _post = await self._run(_video(), [_status("failed", error="out of capacity")])
        assert result.data["error"] == f"WaveSpeed run {PREDICTION_ID} failed: out of capacity"
