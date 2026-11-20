"""Verify that NVIDIA components apply the credential destination policy."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from lfx_bundles.nvidia import nvidia_embedding, nvidia_ingest, nvidia_rerank

_NIM_URL = "https://nim.example"
_OPERATOR_KEY = "fixture-operator"  # pragma: allowlist secret
_FLOW_KEY = "fixture-flow"  # pragma: allowlist secret


@pytest.mark.parametrize("key", [_OPERATOR_KEY, ""])
@pytest.mark.parametrize("component", ["embeddings", "rerank"])
@pytest.mark.parametrize("trusted", [False, True])
def test_nim_checks_credentials_before_sdk_construction(monkeypatch, key, component, trusted):
    monkeypatch.setenv("NVIDIA_API_KEY", _OPERATOR_KEY)
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "nim.example" if trusted else "other.example")
    sdk = SimpleNamespace(NVIDIAEmbeddings=Mock(), NVIDIARerank=Mock())
    monkeypatch.setitem(sys.modules, "langchain_nvidia_ai_endpoints", sdk)

    if component == "embeddings":
        node = nvidia_embedding.NVIDIAEmbeddingsComponent(base_url=_NIM_URL, nvidia_api_key=key)
        build = node.build_embeddings
        factory = sdk.NVIDIAEmbeddings
        module = nvidia_embedding
        field = "nvidia_api_key"
    else:
        node = nvidia_rerank.NvidiaRerankComponent(base_url=_NIM_URL, api_key=key)
        build = node.build_compressor
        factory = sdk.NVIDIARerank
        module = nvidia_rerank
        field = "api_key"

    validate_url = Mock()
    protect_redirects = Mock()
    monkeypatch.setattr(module, "validate_provider_base_url", validate_url)
    monkeypatch.setattr(module, "_install_redirect_policy", protect_redirects)

    if trusted:
        assert build() is factory.return_value
        assert factory.call_args.kwargs[field] == (key or None)
        validate_url.assert_called_once()
        protect_redirects.assert_called_once_with()
    else:
        with pytest.raises(ValueError, match="server environment"):
            build()
        factory.assert_not_called()


@pytest.mark.parametrize("api_key", [_OPERATOR_KEY, _FLOW_KEY])
def test_nvidia_ingest_applies_destination_policy_and_redirect_protection(monkeypatch, tmp_path, api_key):
    monkeypatch.setenv("NVIDIA_API_KEY", _OPERATOR_KEY)
    monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "other.example")
    monkeypatch.setattr(nvidia_ingest, "validate_provider_base_url", Mock())
    mock_ingestor = Mock(side_effect=RuntimeError("stop before file processing"))
    monkeypatch.setitem(sys.modules, "nv_ingest_client.client", SimpleNamespace(Ingestor=mock_ingestor))
    node = nvidia_ingest.NvidiaIngestComponent(base_url=_NIM_URL, api_key=api_key)
    file_path = tmp_path / "document.txt"
    file_path.write_text("Example document")
    files = [node.BaseFile(data=[], path=file_path)]

    if api_key == _OPERATOR_KEY:
        with pytest.raises(ValueError, match="server environment"):
            node.process_files(files)
        mock_ingestor.assert_not_called()
    else:
        with pytest.raises(RuntimeError, match="stop before file processing"):
            node.process_files(files)
        with mock_ingestor.call_args.kwargs["message_client_kwargs"]["http_allocator"]() as session:
            assert session.resolve_redirects.__name__ == "resolve_redirects"
            assert "resolve_redirects" in vars(session)
