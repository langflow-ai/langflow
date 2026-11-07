"""Unit tests for the GenMagic media components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the real endpoint paths,
headers, payloads and error handling of the shared client. Nothing here reaches the network, and no
test starts a generation.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from lfx.custom.custom_component.component import Component
from lfx.schema.message import Message
from lfx_bundles.genmagic.genmagic_common import GenMagicAPIError, client_header
from lfx_bundles.genmagic.genmagic_image_generation import GenMagicImageGenerationComponent
from lfx_bundles.genmagic.genmagic_text_to_speech import GenMagicTextToSpeechComponent
from lfx_bundles.genmagic.genmagic_video_generation import GenMagicVideoGenerationComponent
from lfx_bundles.genmagic.genmagic_video_status import GenMagicVideoStatusComponent

from .conftest import API_KEY, api_url, response

if TYPE_CHECKING:
    import httpx

MEDIA_COMPONENTS = [
    GenMagicImageGenerationComponent,
    GenMagicVideoGenerationComponent,
    GenMagicVideoStatusComponent,
    GenMagicTextToSpeechComponent,
]
MODEL_DROPDOWN_COMPONENTS = [
    GenMagicImageGenerationComponent,
    GenMagicVideoGenerationComponent,
    GenMagicTextToSpeechComponent,
]
IMAGE_URL = "https://genmagic.co/media/image-1.png"
VIDEO_URL = "https://genmagic.co/media/video-1.mp4"
AUDIO_URL = "https://genmagic.co/media/speech-1.mp3"
COST_HEADERS = {"X-Cost-Cents": "3.5", "X-Credits-Remaining": "996.5"}


def _image(**values: Any) -> GenMagicImageGenerationComponent:
    component = GenMagicImageGenerationComponent()
    component.set(**{"api_key": API_KEY, "prompt": "a lighthouse at dusk", **values})
    return component


def _video(**values: Any) -> GenMagicVideoGenerationComponent:
    component = GenMagicVideoGenerationComponent()
    component.set(**{"api_key": API_KEY, "prompt": "waves on a beach", **values})
    return component


def _status(**values: Any) -> GenMagicVideoStatusComponent:
    component = GenMagicVideoStatusComponent()
    component.set(**{"api_key": API_KEY, "job_id": "vid_1", **values})
    return component


def _speech(**values: Any) -> GenMagicTextToSpeechComponent:
    component = GenMagicTextToSpeechComponent()
    component.set(**{"api_key": API_KEY, "text": "Hello from Langflow.", **values})
    return component


def _image_reply() -> httpx.Response:
    return response(json_body={"created": 1, "data": [{"url": IMAGE_URL}]}, headers=COST_HEADERS)


@pytest.mark.unit
@pytest.mark.parametrize("component_class", MEDIA_COMPONENTS)
class TestMetadata:
    def test_input_names_do_not_shadow_component_attributes(self, component_class: type[Component]) -> None:
        shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
        assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"

    def test_metadata(self, component_class: type[Component]) -> None:
        component = component_class()
        assert component.icon == "GenMagic"
        assert component.documentation.startswith("https://genmagic.co/")
        api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
        assert api_key.required is True
        assert api_key.value == "GENMAGIC_API_KEY"

    def test_only_the_result_output_is_exposed_as_an_agent_tool(self, component_class: type[Component]) -> None:
        # Each output method would otherwise become its own paid tool for an Agent.
        assert [output.name for output in component_class.outputs if output.tool_mode] == ["result"]


@pytest.mark.unit
@pytest.mark.parametrize("component_class", MODEL_DROPDOWN_COMPONENTS)
def test_model_dropdown_loads_on_mount_and_accepts_any_model_id(component_class: type[Component]) -> None:
    dropdown = next(inp for inp in component_class.inputs if inp.name == "model_name")
    assert dropdown.options == []  # an empty list makes the editor load the live catalog when the node is added
    assert dropdown.refresh_button is True
    assert dropdown.combobox is True
    assert dropdown.value == "auto"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", MODEL_DROPDOWN_COMPONENTS)
def test_catalog_is_fetched_only_for_the_model_dropdown(component_class: type[Component]) -> None:
    build_config = {"model_name": {"options": [], "value": "auto"}}
    with patch("httpx.Client.request") as request:
        component_class().update_build_config(build_config, "", "tool_mode")

    request.assert_not_called()
    assert build_config["model_name"]["options"] == []


@pytest.mark.unit
class TestImageGeneration:
    def test_request_shape_and_outputs(self) -> None:
        component = _image()
        with patch("httpx.Client.request", return_value=_image_reply()) as request:
            result = component.build_result()
            url = component.build_image_url()
            picture = component.build_image()

        assert request.call_count == 1  # one paid request serves every output
        method, endpoint = request.call_args.args
        assert (method, endpoint) == ("POST", api_url("/images/generations"))
        headers = request.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {API_KEY}"
        assert headers["X-GenMagic-Client"] == client_header()
        assert request.call_args.kwargs["json"] == {
            "prompt": "a lighthouse at dusk",
            "size": "1024x1024",
            "response_format": "url",
        }
        assert result.data == {
            "url": IMAGE_URL,
            "model": "auto",
            "prompt": "a lighthouse at dusk",
            "size": "1024x1024",
            "cost_cents": 3.5,
            "balance_cents": 996.5,
        }
        assert url.text == IMAGE_URL
        assert picture.text == f"![a lighthouse at dusk]({IMAGE_URL})"

    def test_model_size_and_reference_image_are_sent(self) -> None:
        component = _image(
            model_name=" vendor/image-1 ", size="1792x1024", reference_image="https://example.com/in.png"
        )
        with patch("httpx.Client.request", return_value=_image_reply()) as request:
            component.build_image_url()

        body = request.call_args.kwargs["json"]
        assert body["model"] == "vendor/image-1"
        assert body["size"] == "1792x1024"
        assert body["image"] == "https://example.com/in.png"

    def test_response_model_and_revised_prompt_are_reported(self) -> None:
        reply = response(json_body={"model": "vendor/image-1", "data": [{"url": IMAGE_URL, "revised_prompt": "r"}]})
        with patch("httpx.Client.request", return_value=reply):
            result = _image().build_result()

        assert result.data["model"] == "vendor/image-1"
        assert result.data["revised_prompt"] == "r"

    def test_prompt_wired_from_another_component_is_accepted(self) -> None:
        component = _image(prompt=Message(text="  a red fox  "))
        with patch("httpx.Client.request", return_value=_image_reply()) as request:
            component.build_image_url()

        assert request.call_args.kwargs["json"]["prompt"] == "a red fox"

    def test_markdown_alt_text_is_cleaned(self) -> None:
        component = _image(prompt="a [bracketed]\nprompt " + "x" * 200)
        with patch("httpx.Client.request", return_value=_image_reply()):
            text = component.build_image().text

        alt = text[2 : text.index("](")]
        assert "[" not in alt
        assert "]" not in alt
        assert "\n" not in alt
        assert len(alt) <= 100

    def test_a_new_build_makes_a_new_request_and_a_changed_prompt_too(self) -> None:
        component = _image()
        with patch("httpx.Client.request", return_value=_image_reply()) as request:
            component.build_image_url()
            component.build_image_url()
            assert request.call_count == 1

            component.set(prompt="a different prompt")
            component.build_image_url()
            assert request.call_count == 2

            component._pre_run_setup()
            component.build_image_url()
            assert request.call_count == 3

    @pytest.mark.parametrize("key", [None, "", "  "])
    def test_missing_key_makes_no_request(self, key) -> None:
        with patch("httpx.Client.request") as request, pytest.raises(GenMagicAPIError, match="API key is required"):
            _image(api_key=key).build_result()

        request.assert_not_called()

    def test_empty_prompt_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request, pytest.raises(GenMagicAPIError, match="Enter a prompt"):
            _image(prompt="   ").build_result()

        request.assert_not_called()

    def test_response_without_an_image_is_an_error(self) -> None:
        with (
            patch("httpx.Client.request", return_value=response(json_body={"data": []})),
            pytest.raises(GenMagicAPIError, match="returned no image"),
        ):
            _image().build_result()

    def test_errors_from_genmagic_are_raised(self) -> None:
        body = {"error": {"message": "Balance would go negative", "code": "insufficient_quota"}}
        with (
            patch("httpx.Client.request", return_value=response(402, json_body=body)),
            pytest.raises(GenMagicAPIError, match="balance is too low"),
        ):
            _image().build_result()

    def test_timeout_input_sets_the_http_timeout(self) -> None:
        with patch("httpx.Client.request", return_value=_image_reply()), patch("httpx.Client") as client_class:
            client_class.return_value.__enter__.return_value.request.return_value = _image_reply()
            _image(timeout=45).build_image_url()

        assert client_class.call_args.kwargs["timeout"] == 45.0

    def test_update_build_config_lists_the_catalog_with_auto_first(self) -> None:
        catalog = {"data": [{"id": "a/old", "created": 1}, {"id": "b/new", "created": 2}]}
        build_config = {"model_name": {"options": [], "value": "auto"}}
        with patch("httpx.Client.request", return_value=response(json_body=catalog)) as request:
            _image().update_build_config(build_config, "auto", "model_name")

        assert build_config["model_name"]["options"] == ["auto", "b/new", "a/old"]
        assert request.call_args.kwargs["params"] == {"category": "image"}
        assert "Authorization" not in request.call_args.kwargs["headers"]


@pytest.mark.unit
class TestVideoGeneration:
    @staticmethod
    def _created(job_id: str = "vid_1") -> httpx.Response:
        return response(202, json_body={"id": job_id, "object": "video.generation", "status": "queued"})

    @staticmethod
    def _done(**job: Any) -> httpx.Response:
        body = {"id": "vid_1", "model": "vendor/video-1", "status": "completed", "url": VIDEO_URL, "cost_cents": 40}
        return response(json_body={**body, **job}, headers={"X-Cost-Cents": "40", "X-Credits-Remaining": "960"})

    def test_starts_the_job_polls_and_returns_the_clip(self, no_sleep) -> None:
        replies = [self._created(), response(json_body={"id": "vid_1", "status": "processing"}), self._done()]
        component = _video()
        with patch("httpx.Client.request", side_effect=replies) as request:
            result = component.build_result()
            url = component.build_video_url()

        assert request.call_count == 3  # create + two polls, shared by both outputs
        first, last = request.call_args_list[0], request.call_args_list[-1]
        assert first.args == ("POST", api_url("/videos"))
        assert first.kwargs["json"] == {"prompt": "waves on a beach", "aspect_ratio": "16:9"}
        assert last.args == ("GET", api_url("/videos/vid_1"))
        assert result.data == {
            "id": "vid_1",
            "model": "vendor/video-1",
            "status": "completed",
            "url": VIDEO_URL,
            "cost_cents": 40.0,
            "balance_cents": 960.0,
            "prompt": "waves on a beach",
            "aspect_ratio": "16:9",
        }
        assert url.text == VIDEO_URL
        assert no_sleep.call_count == 2

    @pytest.mark.usefixtures("no_sleep")
    def test_optional_parameters_are_sent_only_when_set(self) -> None:
        component = _video(
            model_name="vendor/video-1",
            aspect_ratio="9:16",
            duration=8,
            start_image="https://example.com/first.png",
        )
        with patch("httpx.Client.request", side_effect=[self._created(), self._done()]) as request:
            component.build_video_url()

        assert request.call_args_list[0].kwargs["json"] == {
            "prompt": "waves on a beach",
            "aspect_ratio": "9:16",
            "model": "vendor/video-1",
            "duration": 8,
            "image": "https://example.com/first.png",
        }

    @pytest.mark.usefixtures("no_sleep")
    def test_zero_duration_and_auto_model_are_omitted(self) -> None:
        with patch("httpx.Client.request", side_effect=[self._created(), self._done()]) as request:
            _video(duration=0, model_name="auto").build_video_url()

        body = request.call_args_list[0].kwargs["json"]
        assert "duration" not in body
        assert "model" not in body

    @pytest.mark.usefixtures("no_sleep")
    def test_a_failed_render_raises_with_the_reason_and_job_id(self) -> None:
        failed = response(json_body={"id": "vid_1", "status": "failed", "error": "Content was refused"})
        with (
            patch("httpx.Client.request", side_effect=[self._created(), failed]),
            pytest.raises(GenMagicAPIError, match=r"vid_1.*Content was refused"),
        ):
            _video().build_result()

    def test_timeout_raises_with_the_job_id(self) -> None:
        processing = response(json_body={"id": "vid_1", "status": "processing"})
        now = iter([0.0, 0.0, 99.0])
        with (
            patch("httpx.Client.request", side_effect=[self._created(), processing]),
            patch("time.sleep"),
            patch("time.monotonic", side_effect=lambda: next(now)),
            pytest.raises(GenMagicAPIError, match=r"vid_1 is still .* after 30 seconds"),
        ):
            _video(timeout=30).build_result()

    @pytest.mark.usefixtures("no_sleep")
    def test_completed_without_a_url_is_an_error(self) -> None:
        done = response(json_body={"id": "vid_1", "status": "completed"})
        with (
            patch("httpx.Client.request", side_effect=[self._created(), done]),
            pytest.raises(GenMagicAPIError, match="returned no URL"),
        ):
            _video().build_result()

    def test_start_errors_are_raised_before_any_polling(self) -> None:
        body = {"error": {"message": "model_not_supported", "code": "model_not_supported"}}
        with (
            patch("httpx.Client.request", return_value=response(400, json_body=body)) as request,
            pytest.raises(GenMagicAPIError, match="model_not_supported"),
        ):
            _video(model_name="vendor/editor").build_result()

        assert request.call_count == 1

    @pytest.mark.parametrize(
        ("values", "message"),
        [({"api_key": ""}, "API key is required"), ({"prompt": ""}, "Enter a prompt")],
    )
    def test_missing_key_or_prompt_makes_no_request(self, values, message) -> None:
        with patch("httpx.Client.request") as request, pytest.raises(GenMagicAPIError, match=message):
            _video(**values).build_result()

        request.assert_not_called()

    def test_update_build_config_keeps_only_text_to_video_models(self) -> None:
        catalog = {
            "data": [
                {"id": "v/text", "created": 3, "capabilities": {"text_to_video": True}},
                {"id": "v/editor", "created": 2, "capabilities": {"text_to_video": False}},
                {"id": "v/unknown", "created": 1},
            ]
        }
        build_config = {"model_name": {"options": [], "value": "auto"}}
        with patch("httpx.Client.request", return_value=response(json_body=catalog)) as request:
            _video().update_build_config(build_config, "auto", "model_name")

        assert build_config["model_name"]["options"] == ["auto", "v/text", "v/unknown"]
        assert request.call_args.kwargs["params"] == {"category": "video"}


@pytest.mark.unit
class TestVideoStatus:
    def test_completed_job(self) -> None:
        done = response(
            json_body={"id": "vid_1", "status": "completed", "url": VIDEO_URL, "cost_cents": 40},
            headers={"X-Credits-Remaining": "960"},
        )
        component = _status()
        with patch("httpx.Client.request", return_value=done) as request:
            result = component.build_result()
            url = component.build_video_url()

        assert request.call_count == 1
        assert request.call_args.args == ("GET", api_url("/videos/vid_1"))
        assert result.data == {
            "id": "vid_1",
            "status": "completed",
            "url": VIDEO_URL,
            "cost_cents": 40,
            "balance_cents": 960.0,
        }
        assert url.text == VIDEO_URL

    def test_job_still_rendering_is_reported_not_raised(self) -> None:
        processing = response(json_body={"id": "vid_1", "status": "processing"})
        component = _status()
        with patch("httpx.Client.request", return_value=processing):
            result = component.build_result()
            url = component.build_video_url()

        assert result.data == {"id": "vid_1", "status": "processing"}
        assert url.text == ""

    def test_failed_job_is_reported_with_its_error(self) -> None:
        failed = response(json_body={"id": "vid_1", "status": "failed", "error": "Content was refused"})
        with patch("httpx.Client.request", return_value=failed):
            result = _status().build_result()

        assert result.data == {"id": "vid_1", "status": "failed", "error": "Content was refused"}

    def test_wait_polls_until_the_video_is_done(self, no_sleep) -> None:
        replies = [
            response(json_body={"id": "vid_1", "status": "queued"}),
            response(json_body={"id": "vid_1", "status": "processing"}),
            response(json_body={"id": "vid_1", "status": "completed", "url": VIDEO_URL}),
        ]
        with patch("httpx.Client.request", side_effect=replies) as request:
            result = _status(wait=120).build_result()

        assert result.data["url"] == VIDEO_URL
        assert request.call_count == 3
        assert no_sleep.call_count == 2

    def test_wait_polls_with_the_given_id_when_the_lookup_omits_it(self, no_sleep) -> None:
        replies = [
            response(json_body={"status": "queued"}),
            response(json_body={"status": "completed", "url": VIDEO_URL}),
        ]
        with patch("httpx.Client.request", side_effect=replies) as request:
            result = _status(wait=120).build_result()

        assert result.data["url"] == VIDEO_URL
        assert result.data["id"] == "vid_1"
        assert request.call_args_list[1].args == ("GET", api_url("/videos/vid_1"))
        assert no_sleep.call_count == 1

    def test_wait_that_runs_out_reports_the_latest_state(self) -> None:
        replies = [
            response(json_body={"id": "vid_1", "status": "queued"}),
            response(json_body={"id": "vid_1", "status": "processing"}),
        ]
        now = iter([0.0, 0.0, 99.0])
        with (
            patch("httpx.Client.request", side_effect=replies),
            patch("time.sleep"),
            patch("time.monotonic", side_effect=lambda: next(now)),
        ):
            result = _status(wait=30).build_result()

        assert result.data == {"id": "vid_1", "status": "processing"}

    def test_unknown_job_is_an_error(self) -> None:
        body = {"error": {"message": "No such job", "code": "not_found"}}
        with (
            patch("httpx.Client.request", return_value=response(404, json_body=body)),
            pytest.raises(GenMagicAPIError, match="No such job"),
        ):
            _status(job_id="vid_nope").build_result()

    def test_empty_job_id_makes_no_request(self) -> None:
        with patch("httpx.Client.request") as request, pytest.raises(GenMagicAPIError, match="Enter the ID"):
            _status(job_id=" ").build_result()

        request.assert_not_called()


@pytest.mark.unit
class TestTextToSpeech:
    @staticmethod
    def _audio(**headers: str) -> httpx.Response:
        return response(content=b"ID3-audio", headers={"Content-Type": "audio/mpeg", **headers})

    def test_request_shape_and_outputs(self) -> None:
        component = _speech()
        reply = self._audio(**{"X-Media-Url": AUDIO_URL, **COST_HEADERS})
        with patch("httpx.Client.request", return_value=reply) as request:
            result = component.build_result()
            url = component.build_audio_url()

        assert request.call_count == 1
        assert request.call_args.args == ("POST", api_url("/audio/speech"))
        assert request.call_args.kwargs["headers"]["Authorization"] == f"Bearer {API_KEY}"
        assert request.call_args.kwargs["json"] == {"input": "Hello from Langflow.", "voice": "alloy"}
        assert result.data == {
            "model": "auto",
            "voice": "alloy",
            "mime_type": "audio/mpeg",
            "cost_cents": 3.5,
            "balance_cents": 996.5,
            "audio_url": AUDIO_URL,
        }
        assert url.text == AUDIO_URL

    def test_model_is_sent_and_an_empty_voice_is_omitted(self) -> None:
        component = _speech(model_name="vendor/tts-1", voice="")
        with patch("httpx.Client.request", return_value=self._audio(**{"X-Media-Url": AUDIO_URL})) as request:
            component.build_audio_url()

        assert request.call_args.kwargs["json"] == {"input": "Hello from Langflow.", "model": "vendor/tts-1"}

    def test_audio_is_kept_inline_when_no_hosted_url_is_returned(self) -> None:
        with patch("httpx.Client.request", return_value=self._audio()):
            result = _speech().build_result()

        assert base64.b64decode(result.data["audio_base64"]) == b"ID3-audio"
        assert "audio_url" not in result.data

    def test_an_empty_audio_body_without_a_url_is_an_error(self) -> None:
        with (
            patch("httpx.Client.request", return_value=response(content=b"")),
            pytest.raises(GenMagicAPIError, match="returned no audio"),
        ):
            _speech().build_result()

    @pytest.mark.parametrize(
        ("values", "message"),
        [({"api_key": ""}, "API key is required"), ({"text": "  "}, "Enter the text")],
    )
    def test_missing_key_or_text_makes_no_request(self, values, message) -> None:
        with patch("httpx.Client.request") as request, pytest.raises(GenMagicAPIError, match=message):
            _speech(**values).build_result()

        request.assert_not_called()

    def test_errors_are_returned_from_a_json_error_body(self) -> None:
        body = {"error": {"message": "Unknown voice", "code": "invalid_request_error"}}
        with (
            patch("httpx.Client.request", return_value=response(400, json_body=body)),
            pytest.raises(GenMagicAPIError, match="Unknown voice"),
        ):
            _speech(voice="nope").build_result()

    def test_update_build_config_keeps_only_speech_models(self) -> None:
        catalog = {
            "data": [
                {"id": "g/music", "created": 4, "audio_kind": "music"},
                {"id": "o/speech", "created": 3, "audio_kind": "speech"},
                {"id": "o/untyped", "created": 2},
            ]
        }
        build_config = {"model_name": {"options": [], "value": "auto"}}
        with patch("httpx.Client.request", return_value=response(json_body=catalog)) as request:
            _speech().update_build_config(build_config, "auto", "model_name")

        assert build_config["model_name"]["options"] == ["auto", "o/speech", "o/untyped"]
        assert request.call_args.kwargs["params"] == {"category": "audio"}
