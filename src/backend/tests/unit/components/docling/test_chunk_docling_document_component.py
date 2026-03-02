"""Tests for ChunkDoclingDocumentComponent HybridChunker parameters."""

import sys
import types

import pytest

pytest.importorskip("tiktoken")
pytest.importorskip("docling_core")

from lfx.components.docling.chunk_docling_document import ChunkDoclingDocumentComponent


def _base_build_config():
    return {
        "chunker": {"value": "HybridChunker"},
        "provider": {"value": "Hugging Face", "show": True},
        "hf_model_name": {"show": True},
        "openai_model_name": {"show": False},
        "max_tokens": {"show": True},
        "merge_peers": {"show": False},
        "always_emit_headings": {"show": False},
    }


class TestChunkDoclingDocumentComponentBuildConfig:
    def test_update_build_config_hybrid_shows_chunker_fields(self):
        component = ChunkDoclingDocumentComponent()
        build_config = _base_build_config()

        result = component.update_build_config(build_config, field_value="HybridChunker", field_name="chunker")

        assert result["provider"]["show"] is True
        assert result["hf_model_name"]["show"] is True
        assert result["openai_model_name"]["show"] is False
        assert result["max_tokens"]["show"] is True
        assert result["merge_peers"]["show"] is True
        assert result["always_emit_headings"]["show"] is True

    def test_update_build_config_hierarchical_hides_hybrid_fields(self):
        component = ChunkDoclingDocumentComponent()
        build_config = _base_build_config()

        result = component.update_build_config(build_config, field_value="HierarchicalChunker", field_name="chunker")

        assert result["provider"]["show"] is False
        assert result["hf_model_name"]["show"] is False
        assert result["openai_model_name"]["show"] is False
        assert result["max_tokens"]["show"] is False
        assert result["merge_peers"]["show"] is False
        assert result["always_emit_headings"]["show"] is False

    def test_update_build_config_provider_toggle(self):
        component = ChunkDoclingDocumentComponent()
        build_config = _base_build_config()

        result = component.update_build_config(build_config, field_value="OpenAI", field_name="provider")

        assert result["hf_model_name"]["show"] is False
        assert result["openai_model_name"]["show"] is True


class TestChunkDoclingDocumentComponentHybridChunker:
    def _run_chunk_documents_with_mocks(
        self, monkeypatch, *, chunker_name, merge_peers_input, always_emit_headings_input
    ):
        captured = {}

        class DummyHybridChunker:
            def __init__(self, tokenizer, *, merge_peers=False, always_emit_headings=False):
                captured["tokenizer"] = tokenizer
                captured["merge_peers"] = merge_peers
                captured["always_emit_headings"] = always_emit_headings

            def chunk(self, _dl_doc=None, **_kwargs):
                return []

            def contextualize(self, _chunk=None, **_kwargs):
                return ""

        class DummyHierarchicalChunker:
            def __init__(self):
                captured["hierarchical_called"] = True

            def chunk(self, **_kwargs):
                return []

            def contextualize(self, **_kwargs):
                return ""

        class DummyTokenizer:
            @classmethod
            def from_pretrained(cls, model_name, max_tokens=None):
                captured["model_name"] = model_name
                captured["max_tokens"] = max_tokens
                return "tokenizer"

        hybrid_chunker_module = types.ModuleType("docling_core.transforms.chunker.hybrid_chunker")
        hybrid_chunker_module.HybridChunker = DummyHybridChunker
        monkeypatch.setitem(sys.modules, "docling_core.transforms.chunker.hybrid_chunker", hybrid_chunker_module)

        tokenizer_module = types.ModuleType("docling_core.transforms.chunker.tokenizer")
        huggingface_tokenizer_module = types.ModuleType("docling_core.transforms.chunker.tokenizer.huggingface")
        huggingface_tokenizer_module.HuggingFaceTokenizer = DummyTokenizer
        tokenizer_module.huggingface = huggingface_tokenizer_module
        monkeypatch.setitem(sys.modules, "docling_core.transforms.chunker.tokenizer", tokenizer_module)
        monkeypatch.setitem(
            sys.modules,
            "docling_core.transforms.chunker.tokenizer.huggingface",
            huggingface_tokenizer_module,
        )
        monkeypatch.setattr(
            "lfx.components.docling.chunk_docling_document.HierarchicalChunker",
            DummyHierarchicalChunker,
        )
        monkeypatch.setattr(
            "lfx.components.docling.chunk_docling_document.extract_docling_documents",
            lambda *_args, **_kwargs: ([], None),
        )

        component = ChunkDoclingDocumentComponent()
        component._attributes = {
            "data_inputs": None,
            "chunker": chunker_name,
            "provider": "Hugging Face",
            "hf_model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "max_tokens": 256,
            "merge_peers": merge_peers_input,
            "always_emit_headings": always_emit_headings_input,
            "doc_key": "doc",
        }
        component.chunk_documents()
        return captured

    @pytest.mark.parametrize(
        ("merge_peers_input", "expected_merge_peers"),
        [
            (True, True),
            (False, False),
            (1, True),
            (0, False),
            (None, False),
        ],
    )
    def test_hybrid_chunker_receives_merge_peers(self, monkeypatch, merge_peers_input, expected_merge_peers):
        captured = self._run_chunk_documents_with_mocks(
            monkeypatch,
            chunker_name="HybridChunker",
            merge_peers_input=merge_peers_input,
            always_emit_headings_input=False,
        )
        assert captured["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert captured["max_tokens"] == 256
        assert captured["merge_peers"] is expected_merge_peers

    @pytest.mark.parametrize(
        ("always_emit_headings_input", "expected_always_emit_headings"),
        [
            (True, True),
            (False, False),
            (1, True),
            (0, False),
            (None, False),
        ],
    )
    def test_hybrid_chunker_receives_always_emit_headings(
        self, monkeypatch, always_emit_headings_input, expected_always_emit_headings
    ):
        captured = self._run_chunk_documents_with_mocks(
            monkeypatch,
            chunker_name="HybridChunker",
            merge_peers_input=True,
            always_emit_headings_input=always_emit_headings_input,
        )
        assert captured["always_emit_headings"] is expected_always_emit_headings

    def test_hierarchical_chunker_instantiates_without_hybrid_kwargs(self, monkeypatch):
        captured = self._run_chunk_documents_with_mocks(
            monkeypatch,
            chunker_name="HierarchicalChunker",
            merge_peers_input=True,
            always_emit_headings_input=True,
        )
        assert captured["hierarchical_called"] is True
