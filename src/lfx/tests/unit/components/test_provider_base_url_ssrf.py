"""SSRF regression tests for components that fetch a tenant-controlled base_url.

These cover the multi-tenant hole where Home Assistant, Ollama and LM Studio components
fetched a tenant-supplied ``base_url`` (at run time and during build-config edits) with no
SSRF guard, enabling cloud-metadata credential theft / internal-network probing.

The key assertion is that the outbound request is NEVER issued when the host is blocked.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest


@contextmanager
def ssrf_enabled():
    with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get:
        s = MagicMock()
        s.settings.ssrf_protection_enabled = True
        s.settings.ssrf_allowed_hosts = []
        s.settings.restrict_local_file_access = False
        mock_get.return_value = s
        yield


METADATA_URL = "http://169.254.169.254"


def test_home_assistant_list_states_blocks_metadata_without_request():
    pytest.importorskip("lfx_bundles.homeassistant")
    from lfx.components.homeassistant.list_home_assistant_states import ListHomeAssistantStates

    component = ListHomeAssistantStates()
    with (
        ssrf_enabled(),
        patch("httpx.Client.get") as mock_get,
    ):
        # Trailing '#' would discard the appended /api/states suffix client-side.
        result = component._list_states("token", f"{METADATA_URL}/latest/meta-data/#", "")
        assert mock_get.call_count == 0
        assert isinstance(result, str)
        assert "SSRF" in result


def test_home_assistant_control_blocks_metadata_without_request():
    pytest.importorskip("lfx_bundles.homeassistant")
    from lfx.components.homeassistant.home_assistant_control import HomeAssistantControl

    component = HomeAssistantControl()
    with (
        ssrf_enabled(),
        patch("httpx.Client.post") as mock_post,
    ):
        result = component._control_device("token", f"{METADATA_URL}#", "turn_on", "switch.x")
        assert mock_post.call_count == 0
        assert isinstance(result, str)
        assert "SSRF" in result


async def test_is_valid_ollama_url_blocks_metadata_without_request():
    from lfx.base.models import model_utils

    with (
        ssrf_enabled(),
        patch.object(model_utils.httpx, "AsyncClient") as mock_client,
    ):
        result = await model_utils.is_valid_ollama_url(METADATA_URL)
        assert result is False
        # The client context manager must never have issued a GET.
        assert mock_client.return_value.__aenter__.return_value.get.call_count == 0


async def test_get_ollama_models_blocks_metadata():
    from lfx.base.models import model_utils

    with ssrf_enabled(), pytest.raises(ValueError, match="Could not get model names"):
        await model_utils.get_ollama_models(
            base_url_value=METADATA_URL,
            desired_capability="completion",
            json_models_key="models",
            json_name_key="name",
            json_capabilities_key="capabilities",
        )


async def test_lmstudio_get_model_blocks_metadata():
    pytest.importorskip("lfx_bundles.lmstudio")
    pytest.importorskip("langchain_openai")
    from lfx.components.lmstudio.lmstudiomodel import LMStudioModelComponent

    with ssrf_enabled(), pytest.raises(ValueError, match="Could not retrieve models"):
        await LMStudioModelComponent.get_model(f"{METADATA_URL}/v1")


async def test_lmstudio_embeddings_get_model_blocks_metadata():
    pytest.importorskip("lfx_bundles.lmstudio")
    from lfx.components.lmstudio.lmstudioembeddings import LMStudioEmbeddingsComponent

    with ssrf_enabled(), pytest.raises(ValueError, match="Could not retrieve models"):
        await LMStudioEmbeddingsComponent.get_model(f"{METADATA_URL}/v1")
