import pytest

from langflow.components.langchain_utilities import RunnableExecComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestRunnableExecComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return RunnableExecComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Test input",
            "runnable": Mock(spec=AgentExecutor),
            "input_key": "input",
            "output_key": "output",
            "use_stream": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_get_output_with_valid_keys(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = {"output": "Test output"}
        output_value, status = component.get_output(result, "input", "output")
        assert output_value == "Test output"
        assert status == ""

    def test_get_output_with_warning(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = {"response": "Test response"}
        output_value, status = component.get_output(result, "input", "output")
        assert output_value == "Test response"
        assert "Warning" in status

    def test_get_input_dict_with_valid_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        runnable = Mock()
        runnable.input_keys = ["input"]
        input_dict, status = component.get_input_dict(runnable, "input", "Test input")
        assert input_dict == {"input": "Test input"}
        assert status == ""

    def test_get_input_dict_with_invalid_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        runnable = Mock()
        runnable.input_keys = ["other_input"]
        input_dict, status = component.get_input_dict(runnable, "input", "Test input")
        assert input_dict == {"other_input": "Test input"}
        assert "Warning" in status

    async def test_build_executor(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        mock_runnable = Mock(spec=AgentExecutor)
        mock_runnable.ainvoke.return_value = {"output": "Test output"}
        component.runnable = mock_runnable
        result = await component.build_executor()
        assert result == "Test output"
        mock_runnable.ainvoke.assert_called_once_with({"input": "Test input"})

    async def test_build_executor_type_error(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.runnable = "invalid_runnable"
        with pytest.raises(TypeError, match="The runnable must be an AgentExecutor"):
            await component.build_executor()
