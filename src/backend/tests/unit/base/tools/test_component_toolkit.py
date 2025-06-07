import os

import pytest
from langflow.base.tools.component_tool import ComponentToolkit
from langflow.components.input_output.chat_output import ChatOutput
from langflow.components.langchain_utilities import ToolCallingAgentComponent
from langflow.components.languagemodels import OpenAIModelComponent
from langflow.components.tools.calculator import CalculatorToolComponent
from langflow.graph.graph.base import Graph
from langflow.schema.data import Data
from pydantic import BaseModel


def test_component_tool():
    calculator_component = CalculatorToolComponent()
    component_toolkit = ComponentToolkit(component=calculator_component)
    component_tool = component_toolkit.get_tools()[0]
    assert component_tool.name == "run_model"
    assert issubclass(component_tool.args_schema, BaseModel)
    # TODO: fix this
    # assert component_tool.args_schema.model_json_schema()["properties"] == {
    #     "input_value": {
    #         "default": "",
    #         "description": "Message to be passed as input.",
    #         "title": "Input Value",
    #         "type": "string",
    #     },
    # }
    assert component_toolkit.component == calculator_component

    result = component_tool.invoke(input={"expression": "1+1"})
    assert isinstance(result[0], Data)
    assert "result" in result[0].data
    assert result[0].result == "2"


@pytest.mark.api_key_required
@pytest.mark.usefixtures("client")
async def test_component_tool_with_api_key():
    chat_output = ChatOutput()
    openai_llm = OpenAIModelComponent()
    openai_llm.set(api_key=os.environ["OPENAI_API_KEY"])
    tool_calling_agent = ToolCallingAgentComponent()

    tool_calling_agent.set(
        llm=openai_llm.build_model,
        tools=[chat_output.to_toolkit],
        input_value="Which tools are available? Please tell its name.",
    )

    g = Graph(start=tool_calling_agent, end=tool_calling_agent)
    g.session_id = "test"
    assert g is not None
    results = [result async for result in g.async_start()]
    assert len(results) == 4
    assert "message_response" in tool_calling_agent._outputs_map["response"].value.get_text()
