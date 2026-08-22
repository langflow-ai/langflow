"""Offline unit tests for the Magic Hour bundle (httpx is mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

pytest.importorskip("lfx_bundles")

from lfx_bundles.magic_hour._api import MagicHourError, resolve_image_asset, wait_for_project
from lfx_bundles.magic_hour.magic_hour_image_generator import MagicHourImageGeneratorComponent
from lfx_bundles.magic_hour.magic_hour_image_to_video import MagicHourImageToVideoComponent
from lfx_bundles.magic_hour.magic_hour_text_to_video import MagicHourTextToVideoComponent

VIDEO_URL = "https://videos.magichour.ai/out.mp4"
IMAGE_URL = "https://images.magichour.ai/out.png"


def _response(status_code: int, payload):
    request = httpx.Request("GET", "https://api.magichour.ai/v1/x")
    return httpx.Response(status_code, json=payload, request=request)


def _mock_client(post_payloads=(), get_payloads=()):
    """Build a patched ``httpx.Client`` whose post/get return the given bodies in order."""
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.post.side_effect = [_response(200, p) for p in post_payloads]
    client.get.side_effect = [_response(200, p) for p in get_payloads]
    client.put.return_value = _response(200, {})
    return client


@pytest.mark.unit
class TestMagicHourTextToVideo:
    def test_generates_video_and_polls_until_complete(self):
        component = MagicHourTextToVideoComponent(
            api_key="test-key", prompt="a fox in snow", model="wan-2.2", duration=5, resolution="480p"
        )
        client = _mock_client(
            post_payloads=[{"id": "vid_1", "credits_charged": 120}],
            get_payloads=[
                {"id": "vid_1", "status": "rendering", "downloads": []},
                {
                    "id": "vid_1",
                    "status": "complete",
                    "downloads": [{"url": VIDEO_URL, "expires_at": "2030-01-01"}],
                    "credits_charged": 120,
                    "width": 854,
                    "height": 480,
                    "fps": 24,
                },
            ],
        )
        with (
            patch("lfx_bundles.magic_hour._api.httpx.Client", return_value=client),
            patch("lfx_bundles.magic_hour._api.time.sleep") as sleep,
        ):
            result = component.generate_video()

        assert result.data["project_id"] == "vid_1"
        assert result.data["status"] == "complete"
        assert result.data["video_url"] == VIDEO_URL
        assert result.data["credits_charged"] == 120
        assert sleep.call_count == 1

        _, kwargs = client.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        body = kwargs["json"]
        assert body["model"] == "wan-2.2"
        assert body["end_seconds"] == 5.0
        assert body["resolution"] == "480p"
        assert body["aspect_ratio"] == "16:9"
        assert body["style"] == {"prompt": "a fox in snow"}
        assert client.post.call_args[0][0] == "https://api.magichour.ai/v1/text-to-video"

    def test_video_url_message_output(self):
        component = MagicHourTextToVideoComponent(api_key="k", prompt="p")
        client = _mock_client(
            post_payloads=[{"id": "vid_2", "credits_charged": 120}],
            get_payloads=[{"id": "vid_2", "status": "complete", "downloads": [{"url": VIDEO_URL}]}],
        )
        with patch("lfx_bundles.magic_hour._api.httpx.Client", return_value=client):
            message = component.video_url_message()
        assert message.text == VIDEO_URL

    def test_no_wait_returns_project_id_only(self):
        component = MagicHourTextToVideoComponent(api_key="k", prompt="p", wait_for_completion=False)
        client = _mock_client(post_payloads=[{"id": "vid_3", "credits_charged": 120}])
        with patch("lfx_bundles.magic_hour._api.httpx.Client", return_value=client):
            result = component.generate_video()
        assert result.data == {
            "project_id": "vid_3",
            "status": "queued",
            "video_url": None,
            "credits_charged": 120,
            "model": "wan-2.2",
        }
        client.get.assert_not_called()

    def test_http_error_raises(self):
        component = MagicHourTextToVideoComponent(api_key="bad", prompt="p")
        client = _mock_client()
        client.post.side_effect = [_response(401, {"message": "Unauthorized"})]
        with (
            patch("lfx_bundles.magic_hour._api.httpx.Client", return_value=client),
            pytest.raises(MagicHourError, match="401"),
        ):
            component.generate_video()

    def test_failed_render_raises(self):
        client = _mock_client(get_payloads=[{"id": "vid_4", "status": "error", "error": {"message": "boom"}}])
        with (
            patch("lfx_bundles.magic_hour._api.httpx.Client", return_value=client),
            pytest.raises(MagicHourError, match="error"),
        ):
            wait_for_project("k", "video", "vid_4")


@pytest.mark.unit
class TestMagicHourImageToVideo:
    def test_public_url_is_passed_through(self):
        component = MagicHourImageToVideoComponent(
            api_key="k", image="https://example.com/cat.png", prompt="make it dance", duration=5
        )
        client = _mock_client(
            post_payloads=[{"id": "vid_5", "credits_charged": 120}],
            get_payloads=[{"id": "vid_5", "status": "complete", "downloads": [{"url": VIDEO_URL}]}],
        )
        with patch("lfx_bundles.magic_hour._api.httpx.Client", return_value=client):
            result = component.generate_video()
        assert result.data["video_url"] == VIDEO_URL
        body = client.post.call_args[1]["json"]
        assert body["assets"] == {"image_file_path": "https://example.com/cat.png"}
        assert client.post.call_args[0][0] == "https://api.magichour.ai/v1/image-to-video"

    def test_local_file_is_uploaded(self, tmp_path):
        image = tmp_path / "cat.png"
        image.write_bytes(b"\x89PNG")
        client = _mock_client(
            post_payloads=[
                {"items": [{"upload_url": "https://upload.example/abc", "file_path": "api-assets/id/cat.png"}]}
            ]
        )
        with patch("lfx_bundles.magic_hour._api.httpx.Client", return_value=client):
            file_path = resolve_image_asset("k", str(image))
        assert file_path == "api-assets/id/cat.png"
        client.put.assert_called_once()
        assert client.put.call_args[0][0] == "https://upload.example/abc"
        assert client.put.call_args[1]["content"] == b"\x89PNG"

    def test_missing_image_raises(self):
        with pytest.raises(MagicHourError, match="required"):
            resolve_image_asset("k", "")


@pytest.mark.unit
class TestMagicHourImageGenerator:
    def test_generates_images(self):
        component = MagicHourImageGeneratorComponent(
            api_key="k", prompt="a red bicycle", model="default", image_count=2, aspect_ratio="16:9"
        )
        client = _mock_client(
            post_payloads=[{"id": "img_1", "credits_charged": 10}],
            get_payloads=[
                {"id": "img_1", "status": "complete", "downloads": [{"url": IMAGE_URL}, {"url": IMAGE_URL + "?2"}]}
            ],
        )
        with patch("lfx_bundles.magic_hour._api.httpx.Client", return_value=client):
            result = component.generate_images()
        assert result.data["image_urls"] == [IMAGE_URL, IMAGE_URL + "?2"]
        assert result.data["status"] == "complete"
        body = client.post.call_args[1]["json"]
        assert body["image_count"] == 2
        assert body["aspect_ratio"] == "16:9"
        assert client.post.call_args[0][0] == "https://api.magichour.ai/v1/ai-image-generator"

    def test_image_url_message_output(self):
        component = MagicHourImageGeneratorComponent(api_key="k", prompt="p")
        client = _mock_client(
            post_payloads=[{"id": "img_2", "credits_charged": 5}],
            get_payloads=[{"id": "img_2", "status": "complete", "downloads": [{"url": IMAGE_URL}]}],
        )
        with patch("lfx_bundles.magic_hour._api.httpx.Client", return_value=client):
            assert component.image_url_message().text == IMAGE_URL
