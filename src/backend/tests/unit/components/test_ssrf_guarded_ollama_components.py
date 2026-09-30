"""SSRF guard regressions for the Ollama components.

These live apart from ``test_ssrf_guarded_url_components.py`` because Ollama graduated out of
the ``lfx-bundles`` metapackage into ``lfx-ollama``, which *is* a default ``langflow`` dependency.
That file's module-level ``pytest.importorskip("lfx_bundles")`` would skip these in the default
install even though the components are present -- so they guard on ``lfx_ollama`` instead.

They also stay out of ``test_chatollama_component.py`` / ``test_ollama_embeddings_component.py``:
both of those classes carry an autouse ``disable_ssrf_protection`` fixture, which is exactly the
protection under test here.
"""

import sys
from unittest.mock import patch

import pytest

pytest.importorskip("lfx_ollama")

from lfx.components.ollama.ollama import ChatOllamaComponent
from lfx.components.ollama.ollama_embeddings import OllamaEmbeddingsComponent

BLOCKED_URL = "http://169.254.169.254/latest/meta-data"


@pytest.fixture(autouse=True)
def enable_ssrf_protection(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)


# ``ollama.py`` / ``ollama_embeddings.py`` are reachable under several module identities (the
# ``lfx.components.ollama.*`` shim, the canonical ``lfx_ollama.components.ollama.*``, and the
# runtime ``_lfx_ext.*`` ext-loader copy). Patch on the module the imported class actually lives
# in -- a fixed string target misses when an earlier test in the suite resolves it elsewhere.
_OLLAMA_MODULE = sys.modules[ChatOllamaComponent.__module__]
_OLLAMA_EMBEDDINGS_MODULE = sys.modules[OllamaEmbeddingsComponent.__module__]


def test_ollama_embeddings_build_blocks_metadata_url_before_sdk_client():
    component = OllamaEmbeddingsComponent(base_url=BLOCKED_URL, model_name="model")

    with (
        patch.object(_OLLAMA_EMBEDDINGS_MODULE, "OllamaEmbeddings") as mock_embeddings,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_embeddings()

    mock_embeddings.assert_not_called()


def test_ollama_build_blocks_metadata_url_before_sdk_client():
    component = ChatOllamaComponent(base_url=BLOCKED_URL, model_name="model", mirostat="Disabled")

    with (
        patch.object(_OLLAMA_MODULE, "ChatOllama") as mock_chat_ollama,
        pytest.raises(ValueError, match="SSRF Protection"),
    ):
        component.build_model()

    mock_chat_ollama.assert_not_called()
