from langflow.components.input_output import ChatOutput
from langflow.memory import aget_messages
from langflow.schema.message import Message

from tests.integration.utils import run_single_component


async def test_string():
    outputs = await run_single_component(ChatOutput, inputs={"input_value": "hello"})
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "hello"
    assert outputs["message"].sender == "Machine"
    assert outputs["message"].sender_name == "AI"


async def test_message():
    outputs = await run_single_component(ChatOutput, inputs={"input_value": Message(text="hello")})
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "hello"
    assert outputs["message"].sender == "Machine"
    assert outputs["message"].sender_name == "AI"


async def test_do_not_store_message():
    session_id = "test-session-id"
    outputs = await run_single_component(
        ChatOutput, inputs={"input_value": Message(text="hello"), "should_store_message": True}, session_id=session_id
    )
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "hello"

    assert len(await aget_messages(session_id=session_id)) == 1
    session_id = "test-session-id-another"

    outputs = await run_single_component(
        ChatOutput, inputs={"input_value": Message(text="hello"), "should_store_message": False}, session_id=session_id
    )
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "hello"

    assert len(await aget_messages(session_id=session_id)) == 0
