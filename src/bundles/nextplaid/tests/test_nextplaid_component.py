"""Unit tests for the NextPlaid extension bundle (``lfx-nextplaid``).

The components used to live at ``lfx.components.nextplaid`` /
``lfx.components.vllm`` and are now extracted into a standalone bundle;
these tests travel with the bundle and import the public bundle entry
point.  They exercise only the server-free surface (construction, template
defaults, and the pure embedding-impl helpers) -- the ingestion / search
paths require a running NextPlaid and vLLM server and are covered by the
end-to-end smoke test in the PR description.
"""

import pytest
from lfx_nextplaid import NextPlaidVectorStoreComponent, VllmMultivectorEmbeddingsComponent
from lfx_nextplaid.components.nextplaid.vllm_multivector_impl import VllmMultivectorEmbeddings


def test_bundle_entrypoint_exports():
    assert NextPlaidVectorStoreComponent.__name__ == "NextPlaidVectorStoreComponent"
    assert VllmMultivectorEmbeddingsComponent.__name__ == "VllmMultivectorEmbeddingsComponent"


def test_nextplaid_component_template_defaults():
    component = NextPlaidVectorStoreComponent(
        url="http://localhost:8080",
        index_name="langflow",
        _session_id="test-session",
    )
    node = component.to_frontend_node()["data"]["node"]

    assert node["template"]["url"]["value"] == "http://localhost:8080"
    assert node["template"]["index_name"]["value"] == "langflow"
    # nbits is a dropdown that defaults to 4-bit quantization.
    assert node["template"]["nbits"]["value"] == "4"


def test_vllm_multivector_embeddings_build():
    component = VllmMultivectorEmbeddingsComponent(
        model_name="answerdotai/answerai-colbert-small-v1",
        api_base="http://localhost:8000",
        api_key="",
        _session_id="test-session",
    )
    embeddings = component.build_embeddings()

    assert isinstance(embeddings, VllmMultivectorEmbeddings)
    assert embeddings.model == "answerdotai/answerai-colbert-small-v1"
    assert embeddings.url == "http://localhost:8000"


def test_embeddings_impl_handles_empty_input():
    """Empty batches short-circuit without touching the network."""
    impl = VllmMultivectorEmbeddings(url="http://localhost:8000/", model="m")

    assert impl.embed_documents([]) == []
    assert impl.embed_images([]) == []
    # Trailing slash on the URL is normalized away.
    assert impl.url == "http://localhost:8000"


def test_embeddings_impl_identity():
    a = VllmMultivectorEmbeddings(url="http://h:1", model="m", api_key="k")
    b = VllmMultivectorEmbeddings(url="http://h:1", model="m", api_key="k")
    c = VllmMultivectorEmbeddings(url="http://h:1", model="other", api_key="k")

    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert "VllmMultivectorEmbeddings(" in repr(a)


def test_stable_image_id_prefers_document_id():
    from lfx.schema.data import Data

    with_id = Data(data={"document_id": "doc-42", "content_type": "image/png"})
    assert NextPlaidVectorStoreComponent._stable_image_id(with_id, "idx", 0) == "doc-42"

    # Without an explicit id, the id is a deterministic hash of the metadata.
    without_id = Data(data={"source": "a.pdf", "page": 3, "content_type": "image/png"})
    first = NextPlaidVectorStoreComponent._stable_image_id(without_id, "idx", 0)
    second = NextPlaidVectorStoreComponent._stable_image_id(without_id, "idx", 0)
    assert first == second
    assert len(first) == 64  # sha256 hex digest


@pytest.mark.parametrize("missing_dep", ["langchain_plaid"])
def test_build_vector_store_requires_langchain_plaid(monkeypatch, missing_dep):
    """A clear ImportError is raised when the langchain-plaid client is absent."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith(missing_dep):
            msg = "No module named 'langchain_plaid'"
            raise ImportError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    component = NextPlaidVectorStoreComponent(url="http://localhost:8080", _session_id="test-session")
    with pytest.raises(ImportError, match="langchain-plaid"):
        component.build_vector_store()
