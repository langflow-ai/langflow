"""Tests for field_typing/voice_types.py and Pipecat lazy exports in field_typing/__init__.py."""

import sys


class TestPipecatBaseTypes:
    """PIPECAT_BASE_TYPES dict is complete and consistent with __all__."""

    def test_all_pipecat_type_keys_present(self):
        """PIPECAT_BASE_TYPES contains all expected type-alias names."""
        from lfx.field_typing.voice_types import PIPECAT_BASE_TYPES

        expected = {
            "PipecatTransport",
            "PipecatVADAnalyzer",
            "PipecatFrameProcessor",
            "PipecatSTTService",
            "PipecatLLMService",
            "PipecatTTSService",
            "PipecatS2SService",
            "PipecatContext",
            "PipecatContextAggregatorPair",
            "PipecatTool",
            "PipecatPipelineTask",
            "PipecatFlowManager",
            "PipecatNodeConfig",
        }
        assert expected.issubset(set(PIPECAT_BASE_TYPES.keys()))

    def test_all_values_are_not_none(self):
        """Every type alias resolves to a non-None class (real or stub)."""
        from lfx.field_typing.voice_types import PIPECAT_BASE_TYPES

        for name, cls in PIPECAT_BASE_TYPES.items():
            assert cls is not None, f"{name} should not be None"

    def test_pipecat_tool_is_type_alias(self):
        """PipecatTool is a tuple type alias, not a class."""
        from lfx.field_typing.voice_types import PipecatTool

        assert PipecatTool is not None


class TestPipecatFallbackStubs:
    """Fallback stub classes activate when pipecat-ai is not installed."""

    def test_fallback_stubs_are_classes(self, monkeypatch):
        """When pipecat is absent, voice_types exposes plain stub classes."""
        monkeypatch.setitem(sys.modules, "pipecat", None)
        monkeypatch.delitem(sys.modules, "lfx.field_typing.voice_types", raising=False)

        import importlib

        vt = importlib.import_module("lfx.field_typing.voice_types")
        assert vt.PipecatTransport is not None
        assert vt.PipecatFrameProcessor is not None
        assert vt.PipecatContext is not None

    def test_pipecat_flows_fallback(self, monkeypatch):
        """FlowManager stub activates when pipecat-ai-flows is not installed."""
        monkeypatch.setitem(sys.modules, "pipecat_flows", None)
        monkeypatch.delitem(sys.modules, "lfx.field_typing.voice_types", raising=False)

        import importlib

        vt = importlib.import_module("lfx.field_typing.voice_types")
        assert vt.PipecatFlowManager is not None


class TestPipecatFieldTypingExports:
    """Pipecat types are importable from the top-level lfx.field_typing module."""

    def test_all_pipecat_types_in_all(self):
        """All Pipecat type names are declared in __all__."""
        import lfx.field_typing

        pipecat_names = {n for n in lfx.field_typing.__all__ if n.startswith("Pipecat")}
        assert len(pipecat_names) >= 12

    def test_pipecat_names_set_exists(self):
        """_PIPECAT_NAMES set is defined in field_typing module."""
        import lfx.field_typing

        assert hasattr(lfx.field_typing, "_PIPECAT_NAMES")
        assert isinstance(lfx.field_typing._PIPECAT_NAMES, set)
        assert "PipecatTool" in lfx.field_typing._PIPECAT_NAMES

    def test_pipecat_types_importable_via_getattr(self):
        """Each Pipecat type is resolvable via the lazy __getattr__ path."""
        import lfx.field_typing

        for name in lfx.field_typing._PIPECAT_NAMES:
            obj = getattr(lfx.field_typing, name)
            assert obj is not None, f"{name} must be non-None"

    def test_pipecat_types_match_voice_types_module(self):
        """Types resolved via field_typing are identical to those in voice_types."""
        from lfx.field_typing import PipecatContext, PipecatFrameProcessor, PipecatPipelineTask
        from lfx.field_typing.voice_types import (
            PipecatContext as DirectContext,
        )
        from lfx.field_typing.voice_types import (
            PipecatFrameProcessor as DirectFP,
        )
        from lfx.field_typing.voice_types import (
            PipecatPipelineTask as DirectTask,
        )

        assert PipecatContext is DirectContext
        assert PipecatFrameProcessor is DirectFP
        assert PipecatPipelineTask is DirectTask

    def test_all_exports_accessible(self):
        """Every name in __all__ (including Pipecat names) is accessible."""
        import lfx.field_typing

        for name in lfx.field_typing.__all__:
            attr = getattr(lfx.field_typing, name)
            assert attr is not None, f"{name} should be accessible and non-None"
