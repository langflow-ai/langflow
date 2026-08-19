"""SSRF regression coverage for the vLLM multivector embeddings endpoint.

The ``url`` passed to ``VllmMultivectorEmbeddings`` comes from a tenant-editable component
field, and every ``/pooling`` request carries ``api_key`` in an Authorization header.
"""

from unittest.mock import patch

import pytest
from lfx_nextplaid.components.nextplaid.vllm_multivector_impl import VllmMultivectorEmbeddings

_FAKE_VLLM_API_KEY = "not-a-real-key"  # pragma: allowlist secret


class TestVllmMultivectorSSRF:
    @pytest.mark.parametrize(
        "blocked_url",
        [
            "http://169.254.169.254/latest/meta-data",
            "http://10.0.0.5:8000",
            "http://192.168.1.10:8000",
            "http://172.16.0.9:8000",
        ],
    )
    def test_should_block_internal_endpoint(self, blocked_url):
        """Constructing against an internal host must fail before any request is made."""
        with patch("requests.post") as mock_post:
            with pytest.raises(ValueError, match="SSRF Protection"):
                VllmMultivectorEmbeddings(url=blocked_url, model="test-model", api_key=_FAKE_VLLM_API_KEY)

            mock_post.assert_not_called()

    def test_should_allow_local_vllm_server(self):
        """The default local vLLM endpoint keeps working (loopback exemption)."""
        embeddings = VllmMultivectorEmbeddings(url="http://localhost:8000", model="test-model")

        assert embeddings.url == "http://localhost:8000"

    def test_should_respect_global_ssrf_kill_switch(self, monkeypatch):
        """Operators who disable SSRF protection keep the previous unvalidated behavior."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")

        embeddings = VllmMultivectorEmbeddings(url="http://10.0.0.5:8000", model="test-model")

        assert embeddings.url == "http://10.0.0.5:8000"
