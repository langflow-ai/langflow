import pytest

from langflow.components.agents.CrewAIAgent import CrewAIAgentComponent
from langflow.components.helpers.SequentialTask import SequentialTaskComponent
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs import ChatOutput


@pytest.fixture
def client():
    pass


def test_set_invalid_output():
    chatinput = ChatInput()
    chatoutput = ChatOutput()
    with pytest.raises(ValueError):
        chatoutput.set(input_value=chatinput.build_config)


def test_set_component():
    crewai_agent = CrewAIAgentComponent()
    task = SequentialTaskComponent()
    task.set(agent=crewai_agent)
    assert task._edges[0]["source"] == crewai_agent._id
    assert crewai_agent in task._components
