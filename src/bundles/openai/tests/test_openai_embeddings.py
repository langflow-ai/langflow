"""Regression coverage for the OpenAI Embeddings component's constructor arguments.

``OpenAIEmbeddings`` only builds its own SDK client — and only applies ``api_key``,
``base_url``, ``organization``, ``timeout``, ``max_retries``, ``default_headers``,
``default_query`` and the SSRF-pinned ``http_client`` — inside ``if not self.client``.
Handing it a client therefore silently drops every one of those, and the field this
component exposed could only ever hold a string, so the next call raised
``AttributeError: 'str' object has no attribute 'create'``.

``deployment`` was stored on the model but never read: requests go out against ``model``.
"""

from unittest.mock import patch

from lfx_openai.components.openai.openai import OpenAIEmbeddingsComponent

_FAKE_OPENAI_API_KEY = "sk-not-a-real-key"  # pragma: allowlist secret


def _component() -> OpenAIEmbeddingsComponent:
    component = OpenAIEmbeddingsComponent()
    component.openai_api_base = None
    component.openai_api_key = _FAKE_OPENAI_API_KEY
    component.model = "text-embedding-3-small"
    component.dimensions = None
    component.openai_api_version = None
    component.openai_api_type = None
    component.openai_proxy = None
    component.embedding_ctx_length = 1536
    component.openai_organization = None
    component.chunk_size = 1000
    component.max_retries = 3
    component.request_timeout = None
    component.tiktoken_enable = True
    component.tiktoken_model_name = None
    component.show_progress_bar = False
    component.model_kwargs = {}
    component.skip_empty = False
    component.default_headers = None
    component.default_query = None
    return component


def test_client_and_deployment_are_not_exposed_as_inputs():
    """Neither field had a usable value, so neither should be offered in the UI."""
    names = {input_.name for input_ in OpenAIEmbeddingsComponent.inputs}
    assert "client" not in names
    assert "deployment" not in names


@patch("lfx_openai.components.openai.openai.OpenAIEmbeddings")
def test_build_embeddings_does_not_pass_client_or_deployment(mock_embeddings):
    """Passing either one would suppress the connection parameters below it."""
    _component().build_embeddings()

    kwargs = mock_embeddings.call_args.kwargs
    assert "client" not in kwargs
    assert "deployment" not in kwargs


@patch("lfx_openai.components.openai.openai.OpenAIEmbeddings")
def test_build_embeddings_still_forwards_the_connection_parameters(mock_embeddings):
    """These are the arguments the dropped ``client`` would have suppressed."""
    _component().build_embeddings()

    kwargs = mock_embeddings.call_args.kwargs
    assert kwargs["api_key"] == _FAKE_OPENAI_API_KEY
    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["max_retries"] == 3
    assert kwargs["chunk_size"] == 1000
