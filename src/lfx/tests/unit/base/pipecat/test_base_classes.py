"""Tests for Pipecat abstract base classes in lfx/base/pipecat/."""

from unittest.mock import MagicMock


class TestPipecatFrameProcessorComponent:
    """PipecatFrameProcessorComponent structure and contract."""

    def test_build_processor_is_abstract_method(self):
        """build_processor is decorated with @abstractmethod."""
        from lfx.base.pipecat.processor import PipecatFrameProcessorComponent

        assert hasattr(PipecatFrameProcessorComponent.build_processor, "__isabstractmethod__")
        assert PipecatFrameProcessorComponent.build_processor.__isabstractmethod__

    def test_category(self):
        """Category is set to 'pipecat'."""
        from lfx.base.pipecat.processor import PipecatFrameProcessorComponent

        assert PipecatFrameProcessorComponent.category == "pipecat"

    def test_trace_type(self):
        """trace_type is set to 'pipecat_processor'."""
        from lfx.base.pipecat.processor import PipecatFrameProcessorComponent

        assert PipecatFrameProcessorComponent.trace_type == "pipecat_processor"

    def test_outputs_declared(self):
        """Component declares exactly one output named 'processor'."""
        from lfx.base.pipecat.processor import PipecatFrameProcessorComponent

        assert len(PipecatFrameProcessorComponent.outputs) == 1
        assert PipecatFrameProcessorComponent.outputs[0].name == "processor"
        assert "PipecatFrameProcessor" in PipecatFrameProcessorComponent.outputs[0].types

    def test_concrete_subclass_works(self):
        """A concrete subclass implementing build_processor can be instantiated."""
        from lfx.base.pipecat.processor import PipecatFrameProcessorComponent

        class ConcreteProcessor(PipecatFrameProcessorComponent):
            def build_processor(self):
                return MagicMock()

        comp = ConcreteProcessor.__new__(ConcreteProcessor)
        assert isinstance(comp, PipecatFrameProcessorComponent)


class TestPipecatServiceComponent:
    """PipecatServiceComponent structure, contract, and tool registration."""

    def test_build_service_is_abstract_method(self):
        """build_service is decorated with @abstractmethod."""
        from lfx.base.pipecat.service import PipecatServiceComponent

        assert hasattr(PipecatServiceComponent.build_service, "__isabstractmethod__")
        assert PipecatServiceComponent.build_service.__isabstractmethod__

    def test_category(self):
        from lfx.base.pipecat.service import PipecatServiceComponent

        assert PipecatServiceComponent.category == "pipecat"

    def test_trace_type(self):
        from lfx.base.pipecat.service import PipecatServiceComponent

        assert PipecatServiceComponent.trace_type == "pipecat_service"

    def test_base_inputs_include_api_key_and_tools(self):
        """_base_inputs declares api_key and tools inputs."""
        from lfx.base.pipecat.service import PipecatServiceComponent

        names = {inp.name for inp in PipecatServiceComponent._base_inputs}
        assert "api_key" in names
        assert "tools" in names

    def test_register_tools_calls_register_function(self):
        """_register_tools calls service.register_function for each (schema, handler) tuple."""
        from lfx.base.pipecat.service import PipecatServiceComponent

        class ConcreteService(PipecatServiceComponent):
            def build_service(self):
                return MagicMock()

        comp = ConcreteService.__new__(ConcreteService)

        schema = MagicMock()
        schema.name = "my_tool"
        handler = MagicMock()
        comp.tools = [(schema, handler)]

        service = MagicMock()
        comp._register_tools(service)

        service.register_function.assert_called_once_with("my_tool", handler)

    def test_register_tools_skips_when_no_register_function(self):
        """_register_tools is a no-op when service lacks register_function."""
        from lfx.base.pipecat.service import PipecatServiceComponent

        class ConcreteService(PipecatServiceComponent):
            def build_service(self):
                return MagicMock()

        comp = ConcreteService.__new__(ConcreteService)
        schema = MagicMock()
        schema.name = "t"
        comp.tools = [(schema, MagicMock())]

        service = MagicMock(spec=[])  # no register_function attribute
        comp._register_tools(service)  # must not raise

    def test_register_tools_skips_when_empty_tools(self):
        """_register_tools is a no-op when tools list is empty."""
        from lfx.base.pipecat.service import PipecatServiceComponent

        class ConcreteService(PipecatServiceComponent):
            def build_service(self):
                return MagicMock()

        comp = ConcreteService.__new__(ConcreteService)
        comp.tools = []
        service = MagicMock()
        comp._register_tools(service)
        service.register_function.assert_not_called()


class TestPipecatToolComponent:
    """PipecatToolComponent structure and build_tool packing."""

    def test_build_methods_are_abstract(self):
        """build_function_schema and build_handler are decorated with @abstractmethod."""
        from lfx.base.pipecat.tool import PipecatToolComponent

        assert PipecatToolComponent.build_function_schema.__isabstractmethod__
        assert PipecatToolComponent.build_handler.__isabstractmethod__

    def test_category(self):
        from lfx.base.pipecat.tool import PipecatToolComponent

        assert PipecatToolComponent.category == "pipecat"

    def test_trace_type(self):
        from lfx.base.pipecat.tool import PipecatToolComponent

        assert PipecatToolComponent.trace_type == "pipecat_tool"

    def test_outputs_declared(self):
        """Component declares exactly one output named 'tool' of type PipecatTool."""
        from lfx.base.pipecat.tool import PipecatToolComponent

        assert len(PipecatToolComponent.outputs) == 1
        assert PipecatToolComponent.outputs[0].name == "tool"
        assert "PipecatTool" in PipecatToolComponent.outputs[0].types

    def test_build_tool_packs_schema_and_handler(self):
        """build_tool returns (schema, handler) tuple from the two abstract methods."""
        from lfx.base.pipecat.tool import PipecatToolComponent

        schema = MagicMock()
        handler = MagicMock()

        class ConcreteTool(PipecatToolComponent):
            def build_function_schema(self):
                return schema

            def build_handler(self):
                return handler

        comp = ConcreteTool.__new__(ConcreteTool)
        result = comp.build_tool()

        assert result == (schema, handler)


class TestPipecatBaseInit:
    """lfx.base.pipecat __init__ re-exports all three base classes."""

    def test_all_three_base_classes_exported(self):
        from lfx.base.pipecat import (
            PipecatFrameProcessorComponent,
            PipecatServiceComponent,
            PipecatToolComponent,
        )

        assert PipecatFrameProcessorComponent is not None
        assert PipecatServiceComponent is not None
        assert PipecatToolComponent is not None
