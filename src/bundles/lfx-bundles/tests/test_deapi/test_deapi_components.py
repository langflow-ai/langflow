"""Unit tests for the deAPI components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real endpoints, headers, payloads, polling and error handling of the client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.deapi import deapi_common
from lfx_bundles.deapi.deapi_common import API_BASE_URL
from lfx_bundles.deapi.deapi_image_generation import DeapiImageGenerationComponent
from lfx_bundles.deapi.deapi_text_to_speech import DeapiTextToSpeechComponent
from lfx_bundles.deapi.deapi_transcription import DeapiTranscriptionComponent
from lfx_bundles.deapi.deapi_video_generation import DeapiVideoGenerationComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-deapi-api-key-placeholder"  # pragma: allowlist secret
REQUEST_ID = "c0ffee00-0000-4000-8000-000000000000"
RESULT_URL = "https://results.deapi.ai/1/result.png?X-Amz-Expires=18000"

ALL_COMPONENTS = [
    DeapiImageGenerationComponent,
    DeapiVideoGenerationComponent,
    DeapiTextToSpeechComponent,
    DeapiTranscriptionComponent,
]

CATALOG = [
    {
        "slug": "Flux1schnell",
        "inference_types": ["txt2img"],
        "info": {
            "defaults": {"steps": 4, "width": 768, "height": 768},
            "limits": {"min_width": 256, "max_width": 2048, "min_height": 256, "max_height": 2048, "max_steps": 10},
        },
    },
    {
        "slug": "gpt-image-2",
        "inference_types": ["txt2img", "img2img"],
        "info": {"defaults": {"width": 1024, "height": 1024}, "limits": {"min_width": 512, "max_width": 2048}},
    },
    {
        "slug": "Ltx2_5_22B_Dist_INT8",
        "inference_types": ["txt2video", "img2video"],
        "info": {
            "defaults": {"fps": 24, "width": 768, "height": 768, "frames": 120},
            "limits": {"min_fps": 24, "max_fps": 24, "min_frames": 49, "max_frames": 241, "max_width": 1344},
        },
    },
    {
        "slug": "Kokoro",
        "inference_types": ["txt2audio"],
        "info": {
            "defaults": {"lang": "en-us", "speed": 1, "voice": "af_alloy", "format": "mp3", "sample_rate": 24000},
            "limits": {"min_speed": 0.5, "max_speed": 2, "output_formats": ["mp3"], "available_ratios": [24000]},
        },
    },
    {"slug": "WhisperLargeV3", "inference_types": ["audio2text", "video2text"], "info": {}},
]


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


class FakeDeapi:
    """Route mocked requests the way the deAPI REST API answers them."""

    def __init__(self, *, jobs: list[dict[str, Any]] | None = None, submit: httpx.Response | None = None) -> None:
        self.jobs = jobs if jobs is not None else [{"status": "done", "result_url": RESULT_URL}]
        self.submit = submit
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def __call__(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append((method, url, kwargs))
        if url == f"{API_BASE_URL}/models":
            return _response(json_body={"data": CATALOG, "meta": {"last_page": 1}})
        if url.startswith(f"{API_BASE_URL}/jobs/"):
            job = self.jobs.pop(0) if len(self.jobs) > 1 else self.jobs[0]
            return _response(json_body={"data": {"request_id": REQUEST_ID, "preview": "base64...", **job}})
        if self.submit is not None:
            return self.submit
        return _response(json_body={"data": {"request_id": REQUEST_ID}})

    def submitted(self) -> tuple[str, dict[str, Any]]:
        """Return the URL and JSON body of the one job submission."""
        posts = [(url, kwargs) for method, url, kwargs in self.calls if method == "POST"]
        assert len(posts) == 1
        url, kwargs = posts[0]
        return url, kwargs["json"]


@pytest.fixture(autouse=True)
def no_sleep():
    with patch.object(deapi_common.time, "sleep"):
        yield


def _component(component_class: type[Component], **values) -> Component:
    component = component_class()
    component.set(**{"api_key": API_KEY, **values})
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_metadata(component_class: type[Component]) -> None:
    component = component_class()
    assert component.icon == "deAPI"
    assert "docs.deapi.ai" in component.documentation
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.value == "DEAPI_API_KEY"
    assert len(component_class.outputs) == 1, "each output runs the job, so a second one would bill twice"


@pytest.mark.unit
class TestImageGeneration:
    def test_generates_with_model_defaults_and_polls_the_job(self) -> None:
        fake = FakeDeapi(jobs=[{"status": "processing"}, {"status": "done", "result_url": RESULT_URL}])
        with patch("httpx.Client.request", side_effect=fake):
            data = _component(DeapiImageGenerationComponent, prompt=" a red fox ").generate_image()

        url, body = fake.submitted()
        assert url == f"{API_BASE_URL}/images/generations"
        assert body == {
            "prompt": "a red fox",
            "model": "Flux1schnell",
            "width": 768,
            "height": 768,
            "steps": 4,
            "seed": -1,
        }
        headers = fake.calls[0][2]["headers"]
        assert headers["Authorization"] == f"Bearer {API_KEY}"
        assert data.text == RESULT_URL
        assert data.data["image_url"] == RESULT_URL
        assert data.data["request_id"] == REQUEST_ID
        assert "preview" not in data.data
        assert sum(1 for _, url, _ in fake.calls if "/jobs/" in url) == 2

    def test_user_values_are_clamped_to_model_limits(self) -> None:
        fake = FakeDeapi()
        component = _component(
            DeapiImageGenerationComponent,
            prompt="fox",
            width=4096,
            height=100,
            steps=50,
            seed=7,
            negative_prompt=" blur ",
        )
        with patch("httpx.Client.request", side_effect=fake):
            component.generate_image()

        _, body = fake.submitted()
        assert body["width"] == 2048
        assert body["height"] == 256
        assert body["steps"] == 10
        assert body["seed"] == 7
        assert body["negative_prompt"] == "blur"

    def test_model_without_steps_default_still_sends_steps(self) -> None:
        # The API requires steps for models that use them and drops it for the others.
        fake = FakeDeapi()
        with patch("httpx.Client.request", side_effect=fake):
            _component(DeapiImageGenerationComponent, prompt="fox", model_name="gpt-image-2").generate_image()

        _, body = fake.submitted()
        assert body["steps"] == 4
        assert (body["width"], body["height"]) == (1024, 1024)

    def test_empty_prompt_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _component(DeapiImageGenerationComponent, prompt="   ").generate_image()

        request.assert_not_called()
        assert data.data["error"] == "Enter a prompt."

    def test_missing_api_key_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request:
            data = _component(DeapiImageGenerationComponent, api_key="", prompt="fox").generate_image()

        request.assert_not_called()
        assert "Enter a deAPI API key" in data.data["error"]

    def test_unknown_model_is_an_error_without_a_submission(self) -> None:
        fake = FakeDeapi()
        with patch("httpx.Client.request", side_effect=fake):
            data = _component(DeapiImageGenerationComponent, prompt="fox", model_name="Kokoro").generate_image()

        assert all(method == "GET" for method, _, _ in fake.calls)
        assert "not available to this deAPI account for txt2img" in data.data["error"]

    def test_failed_job_is_an_error(self) -> None:
        fake = FakeDeapi(jobs=[{"status": "error", "error_reason": "worker crashed", "refunded": True}])
        with patch("httpx.Client.request", side_effect=fake):
            data = _component(DeapiImageGenerationComponent, prompt="fox").generate_image()

        assert data.data["error"] == f"deAPI job {REQUEST_ID} failed: worker crashed. The charge was refunded."

    def test_job_still_running_after_max_wait_returns_request_id(self) -> None:
        fake = FakeDeapi(jobs=[{"status": "processing"}])
        with patch("httpx.Client.request", side_effect=fake):
            data = _component(DeapiImageGenerationComponent, prompt="fox", max_wait=0).generate_image()

        assert data.data["request_id"] == REQUEST_ID
        assert data.data["status"] == "processing"
        assert f"{API_BASE_URL}/jobs/{REQUEST_ID}" in data.data["error"]

    def test_transient_poll_error_is_retried(self) -> None:
        fake = FakeDeapi()
        answers = iter([_response(502, text="bad gateway"), None])

        def flaky(method: str, url: str, **kwargs: Any) -> httpx.Response:
            if "/jobs/" in url:
                answer = next(answers, None)
                if answer is not None:
                    fake.calls.append((method, url, kwargs))
                    return answer
            return fake(method, url, **kwargs)

        with patch("httpx.Client.request", side_effect=flaky):
            data = _component(DeapiImageGenerationComponent, prompt="fox").generate_image()

        assert data.data["image_url"] == RESULT_URL

    def test_repeated_poll_errors_give_up_with_the_request_id(self) -> None:
        fake = FakeDeapi()

        def failing(method: str, url: str, **kwargs: Any) -> httpx.Response:
            if "/jobs/" in url:
                return _response(503, text="unavailable")
            return fake(method, url, **kwargs)

        with patch("httpx.Client.request", side_effect=failing):
            data = _component(DeapiImageGenerationComponent, prompt="fox").generate_image()

        assert data.data["error"].startswith(f"Could not read the status of deAPI job {REQUEST_ID}: deAPI error (503)")

    def test_validation_error_is_returned_and_key_is_redacted(self) -> None:
        submit = _response(422, json_body={"message": f"The width field is invalid for {API_KEY}."})
        fake = FakeDeapi(submit=submit)
        with patch("httpx.Client.request", side_effect=fake):
            data = _component(DeapiImageGenerationComponent, prompt="fox").generate_image()

        error = data.data["error"]
        assert error.startswith("deAPI rejected the request (422): The width field is invalid")
        assert API_KEY not in error

    def test_key_cut_at_the_detail_limit_is_still_redacted(self) -> None:
        submit = _response(500, json_body={"message": "x" * 290 + API_KEY})
        with patch("httpx.Client.request", side_effect=FakeDeapi(submit=submit)):
            data = _component(DeapiImageGenerationComponent, prompt="fox").generate_image()

        assert API_KEY[:10] not in data.data["error"]

    def test_auth_error_is_returned(self) -> None:
        with patch("httpx.Client.request", return_value=_response(401, json_body={"message": "Unauthenticated."})):
            data = _component(DeapiImageGenerationComponent, prompt="fox").generate_image()

        assert data.data["error"] == "deAPI rejected the API key (401): Unauthenticated."

    def test_non_json_response_is_an_error(self) -> None:
        with patch("httpx.Client.request", return_value=_response(text="<html>bad gateway</html>")):
            data = _component(DeapiImageGenerationComponent, prompt="fox").generate_image()

        assert "not JSON" in data.data["error"]

    def test_unreachable_api_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ConnectError("connection refused")):
            data = _component(DeapiImageGenerationComponent, prompt="fox").generate_image()

        assert data.data["error"].startswith("Could not reach the deAPI API: ConnectError")

    def test_timeout_is_an_error(self) -> None:
        with patch("httpx.Client.request", side_effect=httpx.ReadTimeout("slow")):
            data = _component(DeapiImageGenerationComponent, prompt="fox").generate_image()

        assert data.data["error"] == "deAPI request timed out after 60 seconds."


@pytest.mark.unit
class TestModelList:
    def test_refresh_loads_models_for_the_task(self) -> None:
        component = _component(DeapiImageGenerationComponent)
        build_config = {"model_name": {"options": []}}
        with patch("httpx.Client.request", side_effect=FakeDeapi()):
            component.update_build_config(build_config, API_KEY, "api_key")

        assert build_config["model_name"]["options"] == ["Flux1schnell", "gpt-image-2"]

    def test_catalog_error_keeps_the_fallback_list(self) -> None:
        component = _component(DeapiTextToSpeechComponent)
        build_config = {"model_name": {"options": []}}
        with patch("httpx.Client.request", return_value=_response(401, json_body={"message": "Unauthenticated."})):
            component.update_build_config(build_config, "bad-key", "api_key")

        assert build_config["model_name"]["options"][0] == "Kokoro"

    def test_catalog_pages_are_all_read(self) -> None:
        pages = {
            1: {"data": [CATALOG[0]], "meta": {"last_page": 2}},
            2: {"data": [CATALOG[1]], "meta": {"last_page": 2}},
        }
        with patch(
            "httpx.Client.request",
            side_effect=lambda _method, _url, **kwargs: _response(json_body=pages[kwargs["params"]["page"]]),
        ):
            slugs = deapi_common.model_slugs(API_KEY, "txt2img", ["fallback"])

        assert slugs == ["Flux1schnell", "gpt-image-2"]


@pytest.mark.unit
class TestVideoGeneration:
    def test_generates_with_model_defaults(self) -> None:
        fake = FakeDeapi()
        with patch("httpx.Client.request", side_effect=fake):
            data = _component(DeapiVideoGenerationComponent, prompt="a fox in snow", frames=500).generate_video()

        url, body = fake.submitted()
        assert url == f"{API_BASE_URL}/videos/generations"
        assert body == {
            "prompt": "a fox in snow",
            "model": "Ltx2_5_22B_Dist_INT8",
            "width": 768,
            "height": 768,
            "frames": 241,
            "fps": 24,
            "seed": -1,
        }
        assert data.data["video_url"] == RESULT_URL


@pytest.mark.unit
class TestTextToSpeech:
    def test_fills_every_required_field_from_the_model(self) -> None:
        fake = FakeDeapi()
        with patch("httpx.Client.request", side_effect=fake):
            data = _component(DeapiTextToSpeechComponent, text="Hello from Langflow.").generate_speech()

        url, body = fake.submitted()
        assert url == f"{API_BASE_URL}/audio/speech"
        assert body == {
            "text": "Hello from Langflow.",
            "model": "Kokoro",
            "voice": "af_alloy",
            "lang": "en-us",
            "speed": 1.0,
            "format": "mp3",
            "sample_rate": 24000,
        }
        assert data.data["audio_url"] == RESULT_URL

    def test_user_voice_language_and_speed_are_sent(self) -> None:
        fake = FakeDeapi()
        component = _component(DeapiTextToSpeechComponent, text="Hi there.", voice="am_adam", language="en-gb", speed=5)
        with patch("httpx.Client.request", side_effect=fake):
            component.generate_speech()

        _, body = fake.submitted()
        assert (body["voice"], body["lang"], body["speed"]) == ("am_adam", "en-gb", 2.0)


@pytest.mark.unit
class TestTranscription:
    def test_transcribes_a_link_and_returns_the_text(self) -> None:
        fake = FakeDeapi(jobs=[{"status": "done", "result": "Hello world.", "result_url": RESULT_URL}])
        component = _component(DeapiTranscriptionComponent, media_url="https://www.youtube.com/watch?v=jNQXAC9IVRw")
        with patch("httpx.Client.request", side_effect=fake):
            message = component.transcribe()

        url, body = fake.submitted()
        assert url == f"{API_BASE_URL}/audio/transcriptions"
        assert body == {
            "model": "WhisperLargeV3",
            "source_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "include_ts": False,
            "return_result_in_response": True,
        }
        assert message.text == "Hello world."

    @pytest.mark.parametrize(
        "url", ["", "youtube.com/watch?v=x", "file:///etc/passwd", "ftp://example.com/a", "https://[x"]
    )
    def test_rejects_non_http_links_without_a_request(self, url: str) -> None:
        with patch("httpx.Client.request") as request:
            message = _component(DeapiTranscriptionComponent, media_url=url).transcribe()

        request.assert_not_called()
        assert "absolute http(s)" in message.text
