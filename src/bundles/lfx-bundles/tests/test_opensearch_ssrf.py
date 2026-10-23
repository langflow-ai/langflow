"""OpenSearch clients must validate connector URLs before constructing the SDK."""

from importlib import import_module
from unittest.mock import MagicMock, patch

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError

pytest.importorskip("lfx_bundles")

_COMPONENTS = (
    ("lfx_bundles.elastic.opensearch", "OpenSearchVectorStoreComponent"),
    ("lfx_bundles.elastic.opensearch_multimodal", "OpenSearchVectorStoreComponentMultimodalMultiEmbedding"),
)


@pytest.fixture
def connector_settings():
    settings = MagicMock()
    settings.ssrf_protection_enabled = True
    settings.connector_ssrf_validation_enabled = True
    settings.connector_ssrf_allow_loopback = True
    settings.ssrf_allowed_hosts = []
    with patch("lfx.utils.ssrf_protection.get_settings_service") as get_settings:
        get_settings.return_value.settings = settings
        yield settings


@pytest.mark.parametrize(("module_name", "class_name"), _COMPONENTS)
@pytest.mark.parametrize("url", ["http://169.254.169.254", "http://10.0.0.1:9200", "http://[fd00::1]:9200"])
@pytest.mark.usefixtures("connector_settings")
def test_opensearch_blocks_private_targets_before_sdk(module_name: str, class_name: str, url: str) -> None:
    module = import_module(module_name)
    component = getattr(module, class_name)(opensearch_url=url)
    with patch.object(module, "OpenSearch") as client, pytest.raises(SSRFProtectionError):
        component.build_client()
    client.assert_not_called()


@pytest.mark.parametrize(("module_name", "class_name"), _COMPONENTS)
def test_opensearch_loopback_setting_is_enforced(module_name, class_name, connector_settings):
    connector_settings.connector_ssrf_allow_loopback = False
    module = import_module(module_name)
    component = getattr(module, class_name)(opensearch_url="http://127.0.0.1:9200")
    with patch.object(module, "OpenSearch") as client, pytest.raises(SSRFProtectionError):
        component.build_client()
    client.assert_not_called()


@pytest.mark.parametrize(("module_name", "class_name"), _COMPONENTS)
@pytest.mark.parametrize("url", ["http://localhost:9200", "http://10.0.0.1:9200"])
def test_opensearch_allows_loopback_and_explicit_allowlist(module_name, class_name, url, connector_settings):
    connector_settings.ssrf_allowed_hosts = ["10.0.0.1"]
    module = import_module(module_name)
    component = getattr(module, class_name)(opensearch_url=url)
    with patch.object(module, "OpenSearch") as client:
        assert component.build_client() is client.return_value
    assert client.call_args.kwargs["hosts"] == [url]
