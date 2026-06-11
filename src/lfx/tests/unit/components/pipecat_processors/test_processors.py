"""Tests for pipecat_processors components."""

import json

import pytest


class TestLLMContextComponent:
    """LLMContextComponent builds an LLMContext with correct parameters."""

    def test_metadata(self):
        """Component has correct display_name, name and category."""
        from lfx.components.pipecat_processors.llm_context import LLMContextComponent

        assert LLMContextComponent.display_name == "LLM Context"
        assert LLMContextComponent.name == "LLMContext"
        assert LLMContextComponent.category == "pipecat"

    def test_inputs_declared(self):
        """Component declares initial_messages_json and tool_choice inputs."""
        from lfx.components.pipecat_processors.llm_context import LLMContextComponent

        names = {i.name for i in LLMContextComponent.inputs}
        assert "initial_messages_json" in names
        assert "tool_choice" in names

    def test_build_context_empty_messages(self):
        """build_context with empty JSON returns an LLMContext with no messages."""
        pytest.importorskip("pipecat")
        from unittest.mock import MagicMock, patch
        from lfx.components.pipecat_processors.llm_context import LLMContextComponent

        comp = LLMContextComponent.__new__(LLMContextComponent)
        comp.initial_messages_json = ""
        comp.tool_choice = "auto"

        mock_ctx = MagicMock()
        with patch("pipecat.processors.aggregators.llm_context.LLMContext", return_value=mock_ctx) as cls:
            result = comp.build_context()
            cls.assert_called_once_with(messages=None)
            assert result is mock_ctx

    def test_build_context_with_messages(self):
        """build_context passes parsed messages to LLMContext."""
        pytest.importorskip("pipecat")
        from unittest.mock import MagicMock, patch
        from lfx.components.pipecat_processors.llm_context import LLMContextComponent

        comp = LLMContextComponent.__new__(LLMContextComponent)
        comp.initial_messages_json = json.dumps([{"role": "system", "content": "You are helpful."}])
        comp.tool_choice = "auto"

        mock_ctx = MagicMock()
        with patch("pipecat.processors.aggregators.llm_context.LLMContext", return_value=mock_ctx) as cls:
            result = comp.build_context()
            cls.assert_called_once_with(messages=[{"role": "system", "content": "You are helpful."}])
            assert result is mock_ctx

    def test_build_context_with_tool_choice(self):
        """build_context passes tool_choice when it is not 'auto'."""
        pytest.importorskip("pipecat")
        from unittest.mock import MagicMock, patch
        from lfx.components.pipecat_processors.llm_context import LLMContextComponent

        comp = LLMContextComponent.__new__(LLMContextComponent)
        comp.initial_messages_json = ""
        comp.tool_choice = "required"

        mock_ctx = MagicMock()
        with patch("pipecat.processors.aggregators.llm_context.LLMContext", return_value=mock_ctx) as cls:
            comp.build_context()
            cls.assert_called_once_with(messages=None, tool_choice="required")

    def test_build_context_invalid_json_raises(self):
        """build_context raises on invalid JSON regardless of pipecat install."""
        from lfx.components.pipecat_processors.llm_context import LLMContextComponent

        comp = LLMContextComponent.__new__(LLMContextComponent)
        comp.initial_messages_json = "{not valid json"
        comp.tool_choice = "auto"

        with pytest.raises(Exception):
            comp.build_context()

    def test_build_context_non_list_json_raises(self):
        """build_context raises ValueError when JSON is not an array."""
        pytest.importorskip("pipecat")
        from lfx.components.pipecat_processors.llm_context import LLMContextComponent

        comp = LLMContextComponent.__new__(LLMContextComponent)
        comp.initial_messages_json = '{"role": "system"}'
        comp.tool_choice = "auto"

        with pytest.raises(ValueError, match="must be a JSON array"):
            comp.build_context()


class TestSileroVADComponent:
    """SileroVADComponent metadata checks."""

    def test_metadata(self):
        from lfx.components.pipecat_processors.silero_vad import SileroVADComponent

        assert SileroVADComponent.display_name == "Silero VAD"
        assert SileroVADComponent.name == "SileroVAD"
        assert SileroVADComponent.category == "pipecat"

    def test_output_type(self):
        from lfx.components.pipecat_processors.silero_vad import SileroVADComponent

        output_types = {t for o in SileroVADComponent.outputs for t in o.types}
        assert "PipecatVADAnalyzer" in output_types

    def test_has_confidence_input(self):
        from lfx.components.pipecat_processors.silero_vad import SileroVADComponent

        input_names = {i.name for i in SileroVADComponent.inputs}
        assert "confidence" in input_names


class TestMicGateProcessorComponent:
    """MicGateProcessorComponent metadata checks."""

    def test_metadata(self):
        from lfx.components.pipecat_processors.mic_gate import MicGateProcessorComponent

        assert MicGateProcessorComponent.display_name == "Mic Gate"
        assert MicGateProcessorComponent.name == "MicGateProcessor"
        assert MicGateProcessorComponent.category == "pipecat"

    def test_output_type(self):
        from lfx.components.pipecat_processors.mic_gate import MicGateProcessorComponent

        output_types = {t for o in MicGateProcessorComponent.outputs for t in o.types}
        assert "PipecatFrameProcessor" in output_types

    def test_requires_llm_input(self):
        from lfx.components.pipecat_processors.mic_gate import MicGateProcessorComponent

        input_names = {i.name for i in MicGateProcessorComponent.inputs}
        assert "llm" in input_names


class TestLLMContextAggregatorPairComponent:
    """LLMContextAggregatorPairComponent metadata checks."""

    def test_metadata(self):
        from lfx.components.pipecat_processors.llm_context_aggregator_pair import (
            LLMContextAggregatorPairComponent,
        )

        assert LLMContextAggregatorPairComponent.display_name == "LLM Context Aggregator Pair"
        assert LLMContextAggregatorPairComponent.name == "LLMContextAggregatorPair"
        assert LLMContextAggregatorPairComponent.category == "pipecat"

    def test_output_type(self):
        from lfx.components.pipecat_processors.llm_context_aggregator_pair import (
            LLMContextAggregatorPairComponent,
        )

        output_types = {t for o in LLMContextAggregatorPairComponent.outputs for t in o.types}
        assert "PipecatContextAggregatorPair" in output_types
