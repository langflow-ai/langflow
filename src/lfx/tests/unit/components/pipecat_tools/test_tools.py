"""Tests for pipecat_tools components."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestVoiceToolComponent:
    """VoiceToolComponent metadata and handler compilation."""

    def test_metadata(self):
        from lfx.components.pipecat_tools.voice_tool import VoiceToolComponent

        assert VoiceToolComponent.display_name == "Voice Tool"
        assert VoiceToolComponent.name == "VoiceTool"
        assert VoiceToolComponent.category == "pipecat"

    def test_output_type_is_pipecat_tool(self):
        from lfx.components.pipecat_tools.voice_tool import VoiceToolComponent

        types = {t for o in VoiceToolComponent.outputs for t in o.types}
        assert "PipecatTool" in types

    def test_compile_handler_source_returns_callable(self):
        """_compile_handler_source compiles a valid handle function from source code."""
        from lfx.components.pipecat_tools.voice_tool import _compile_handler_source

        code = "async def handle(params):\n    await params.result_callback({'ok': True})\n"
        handler = _compile_handler_source(code)
        assert callable(handler)

    def test_compile_handler_source_raises_on_missing_handle(self):
        """_compile_handler_source raises when handle function is absent."""
        from lfx.components.pipecat_tools.voice_tool import _compile_handler_source

        code = "def not_handle(params): pass\n"
        with pytest.raises((TypeError, ValueError)):
            _compile_handler_source(code)

    def test_compile_handler_source_raises_on_non_callable_handle(self):
        """_compile_handler_source raises when handle is not callable."""
        from lfx.components.pipecat_tools.voice_tool import _compile_handler_source

        code = "handle = 42\n"
        with pytest.raises((TypeError, ValueError)):
            _compile_handler_source(code)

    @pytest.mark.asyncio
    async def test_compiled_handler_is_invokable(self):
        """A compiled async handler can be awaited."""
        from lfx.components.pipecat_tools.voice_tool import _compile_handler_source

        code = "async def handle(params):\n    await params.result_callback({'result': 'ok'})\n"
        handler = _compile_handler_source(code)

        params = MagicMock()
        params.result_callback = AsyncMock()
        await handler(params)
        params.result_callback.assert_awaited_once_with({"result": "ok"})


class TestHTTPAPIToolComponent:
    """HTTPAPIToolComponent metadata and handler logic."""

    def test_metadata(self):
        from lfx.components.pipecat_tools.http_api_tool import HTTPAPIToolComponent

        assert HTTPAPIToolComponent.display_name == "HTTP API Tool"
        assert HTTPAPIToolComponent.name == "HTTPAPITool"
        assert HTTPAPIToolComponent.category == "pipecat"

    def test_output_type_is_pipecat_tool(self):
        from lfx.components.pipecat_tools.http_api_tool import HTTPAPIToolComponent

        types = {t for o in HTTPAPIToolComponent.outputs for t in o.types}
        assert "PipecatTool" in types

    def test_has_required_inputs(self):
        from lfx.components.pipecat_tools.http_api_tool import HTTPAPIToolComponent

        names = {i.name for i in HTTPAPIToolComponent.inputs}
        assert "url" in names
        assert "method" in names
        assert "tool_name" in names
        assert "tool_description" in names

    def test_build_function_schema_returns_schema(self):
        """build_function_schema returns a FunctionSchema with name and description."""
        pytest.importorskip("pipecat")
        from lfx.components.pipecat_tools.http_api_tool import HTTPAPIToolComponent

        comp = HTTPAPIToolComponent.__new__(HTTPAPIToolComponent)
        comp.tool_name = "fetch_data"
        comp.tool_description = "Fetches data from an API."
        schema = comp.build_function_schema()
        assert schema is not None
        assert schema.name == "fetch_data"

    def test_build_handler_returns_callable(self):
        """build_handler returns a callable async function."""
        from lfx.components.pipecat_tools.http_api_tool import HTTPAPIToolComponent

        comp = HTTPAPIToolComponent.__new__(HTTPAPIToolComponent)
        comp.url = "https://example.com/api"
        comp.method = "GET"
        comp.headers_json = "{}"
        comp.timeout_secs = 8.0

        handler = comp.build_handler()
        assert callable(handler)

    @pytest.mark.asyncio
    async def test_build_handler_returns_error_on_network_failure(self):
        """build_handler catches exceptions and returns them via result_callback."""
        from lfx.components.pipecat_tools.http_api_tool import HTTPAPIToolComponent

        comp = HTTPAPIToolComponent.__new__(HTTPAPIToolComponent)
        comp.url = "https://unreachable.invalid"
        comp.method = "GET"
        comp.headers_json = "{}"
        comp.timeout_secs = 1.0

        handler = comp.build_handler()
        params = MagicMock()
        params.arguments = {}
        params.result_callback = AsyncMock()

        await handler(params)

        params.result_callback.assert_awaited_once()
        call_arg = params.result_callback.call_args[0][0]
        assert "error" in call_arg


class TestKnowledgeBaseToolComponent:
    """KnowledgeBaseToolComponent metadata."""

    def test_metadata(self):
        from lfx.components.pipecat_tools.knowledge_base_tool import KnowledgeBaseToolComponent

        assert KnowledgeBaseToolComponent.display_name == "Knowledge Base Tool"
        assert KnowledgeBaseToolComponent.name == "KnowledgeBaseTool"
        assert KnowledgeBaseToolComponent.category == "pipecat"

    def test_output_type_is_pipecat_tool(self):
        from lfx.components.pipecat_tools.knowledge_base_tool import KnowledgeBaseToolComponent

        types = {t for o in KnowledgeBaseToolComponent.outputs for t in o.types}
        assert "PipecatTool" in types

    def test_has_required_inputs(self):
        from lfx.components.pipecat_tools.knowledge_base_tool import KnowledgeBaseToolComponent

        names = {i.name for i in KnowledgeBaseToolComponent.inputs}
        assert "kb_id" in names
        assert "tool_name" in names
