import pytest

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
