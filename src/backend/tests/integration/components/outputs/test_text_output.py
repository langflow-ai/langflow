from lfx.components.input_output import TextOutputComponent
from lfx.schema.message import Message

from tests.integration.utils import run_single_component


async def test():
    outputs = await run_single_component(TextOutputComponent, inputs={"input_value": "hello"})
    assert isinstance(outputs["text"], Message)
    assert outputs["text"].text == "hello"
    assert outputs["text"].sender is None
    assert outputs["text"].sender_name is None


async def test_message():
    outputs = await run_single_component(TextOutputComponent, inputs={"input_value": Message(text="hello")})
    assert isinstance(outputs["text"], Message)
    assert outputs["text"].text == "hello"
    assert outputs["text"].sender is None
    assert outputs["text"].sender_name is None
