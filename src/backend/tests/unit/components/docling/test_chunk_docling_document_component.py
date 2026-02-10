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
        captured = {}

        class DummyHybridChunker:
            def __init__(self, tokenizer, *, merge_peers=False):
                captured["tokenizer"] = tokenizer
                captured["merge_peers"] = merge_peers

            def chunk(self):
                return []

            def contextualize(self):
                return ""

        class DummyTokenizer:
            @classmethod
            def from_pretrained(cls, model_name, max_tokens=None):
                captured["model_name"] = model_name
                captured["max_tokens"] = max_tokens
                return "tokenizer"

        monkeypatch.setitem(
            sys.modules,
            "docling_core.transforms.chunker.hybrid_chunker",
            types.SimpleNamespace(HybridChunker=DummyHybridChunker),
        )
        monkeypatch.setitem(
            sys.modules,
            "docling_core.transforms.chunker.tokenizer.huggingface",
            types.SimpleNamespace(HuggingFaceTokenizer=DummyTokenizer),
        )

        component = ChunkDoclingDocumentComponent()
        component._attributes = {
            "data_inputs": None,
            "chunker": "HybridChunker",
            "provider": "Hugging Face",
            "hf_model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "max_tokens": 256,
            "merge_peers": merge_peers_input,
            "doc_key": "doc",
        }

        monkeypatch.setattr(
            "lfx.components.docling.chunk_docling_document.extract_docling_documents",
            lambda *_args, **_kwargs: ([], None),
        )

        component.chunk_documents()

        assert captured["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert captured["max_tokens"] == 256
        assert captured["merge_peers"] is expected_merge_peers
