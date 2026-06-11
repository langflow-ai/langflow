"""Tests for VoicePipelineComponent."""

import pytest
from unittest.mock import MagicMock, patch


class TestVoicePipelineComponent:
    """VoicePipelineComponent structure and build_task logic."""

    def test_metadata(self):
        from lfx.components.pipecat_pipeline.voice_pipeline import VoicePipelineComponent

        assert VoicePipelineComponent.display_name == "Voice Pipeline"
        assert VoicePipelineComponent.name == "VoicePipeline"
        assert VoicePipelineComponent.category == "pipecat"

    def test_output_type_is_pipeline_task(self):
        from lfx.components.pipecat_pipeline.voice_pipeline import VoicePipelineComponent

        types = {t for o in VoicePipelineComponent.outputs for t in o.types}
        assert "PipecatPipelineTask" in types

    def test_has_required_inputs(self):
        from lfx.components.pipecat_pipeline.voice_pipeline import VoicePipelineComponent

        names = {i.name for i in VoicePipelineComponent.inputs}
        assert "transport" in names
        assert "processors" in names

    def test_build_task_raises_without_processors(self):
        """build_task raises ValueError when processors list is empty."""
        pytest.importorskip("pipecat")
        from lfx.components.pipecat_pipeline.voice_pipeline import VoicePipelineComponent

        comp = VoicePipelineComponent.__new__(VoicePipelineComponent)
        comp.transport = MagicMock()
        comp.processors = []
        comp.llm = None
        comp.tools = []
        comp.enable_metrics = True
        comp.enable_usage_metrics = True
        comp.audio_in_sample_rate = 16000
        comp.audio_out_sample_rate = 16000

        with pytest.raises(ValueError, match="at least one processor"):
            comp.build_task()

    def test_build_task_assembles_pipeline(self):
        """build_task builds Pipeline with transport.input, processors, transport.output."""
        pytest.importorskip("pipecat")
        from lfx.components.pipecat_pipeline.voice_pipeline import VoicePipelineComponent

        comp = VoicePipelineComponent.__new__(VoicePipelineComponent)
        processor = MagicMock()
        transport = MagicMock()
        comp.transport = transport
        comp.processors = [processor]
        comp.llm = None
        comp.tools = []
        comp.enable_metrics = True
        comp.enable_usage_metrics = True
        comp.audio_in_sample_rate = 16000
        comp.audio_out_sample_rate = 16000

        mock_task = MagicMock()
        with (
            patch("pipecat.pipeline.pipeline.Pipeline") as mock_pipeline,
            patch("pipecat.pipeline.task.PipelineTask", return_value=mock_task),
            patch("pipecat.pipeline.task.PipelineParams"),
        ):
            result = comp.build_task()

            mock_pipeline.assert_called_once_with([
                transport.input(),
                processor,
                transport.output(),
            ])
            assert result is mock_task

    def test_register_late_tools_skips_duplicates(self):
        """_register_late_tools does not double-register already-known tools."""
        from lfx.components.pipecat_pipeline.voice_pipeline import VoicePipelineComponent

        comp = VoicePipelineComponent.__new__(VoicePipelineComponent)

        schema = MagicMock()
        schema.name = "my_tool"
        handler = MagicMock()

        llm = MagicMock()
        llm._function_handlers = {"my_tool": handler}  # already registered

        comp._register_late_tools(llm, [(schema, handler)])
        llm.register_function.assert_not_called()

    def test_register_late_tools_registers_new_tool(self):
        """_register_late_tools registers tools not yet in the LLM."""
        from lfx.components.pipecat_pipeline.voice_pipeline import VoicePipelineComponent

        comp = VoicePipelineComponent.__new__(VoicePipelineComponent)

        schema = MagicMock()
        schema.name = "new_tool"
        handler = MagicMock()

        llm = MagicMock()
        llm._function_handlers = {}

        comp._register_late_tools(llm, [(schema, handler)])
        llm.register_function.assert_called_once_with("new_tool", handler)
