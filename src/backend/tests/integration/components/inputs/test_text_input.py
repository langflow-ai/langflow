from langflow.schema.message import Message
from tests.integration.utils import run_single_component

from langflow.components.inputs import TextInputComponent
import pytest


@pytest.mark.asyncio
async def test_text_input():
    outputs = await run_single_component(TextInputComponent, run_input="sample text", input_type="text")
    print(outputs)
    assert isinstance(outputs["text"], Message)
    assert outputs["text"].text == "sample text"
    assert outputs["text"].sender is None
    assert outputs["text"].sender_name is None

    outputs = await run_single_component(TextInputComponent, run_input="", input_type="text")
    assert isinstance(outputs["text"], Message)
    assert outputs["text"].text == ""
    assert outputs["text"].sender is None
    assert outputs["text"].sender_name is None
