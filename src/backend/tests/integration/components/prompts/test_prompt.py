from langflow.components.outputs import ChatOutput
from langflow.components.prompts import Prompt, PromptComponent
from langflow.memory import get_messages
from langflow.schema.message import Message
from tests.integration.utils import run_single_component

from langflow.components.inputs import ChatInput
import pytest


@pytest.mark.asyncio
async def test():
    outputs = await run_single_component(PromptComponent, inputs={
        "template": "test {var1}",
        "var1": "from the var"
    })
    print(outputs)
    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "test from the var"
