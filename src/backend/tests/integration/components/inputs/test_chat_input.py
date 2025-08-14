from lfx.components.input_output import ChatInput
from lfx.memory import aget_messages
from lfx.schema.message import Message
from tests.integration.utils import pyleak_marker, run_single_component

pytestmark = pyleak_marker()


async def test_default():
    outputs = await run_single_component(ChatInput, run_input="hello")
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "hello"
    assert outputs["message"].sender == "User"
    assert outputs["message"].sender_name == "User"

    outputs = await run_single_component(ChatInput, run_input="")
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == ""
    assert outputs["message"].sender == "User"
    assert outputs["message"].sender_name == "User"


async def test_sender():
    outputs = await run_single_component(
        ChatInput, inputs={"sender": "Machine", "sender_name": "AI"}, run_input="hello"
    )
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "hello"
    assert outputs["message"].sender == "Machine"
    assert outputs["message"].sender_name == "AI"


async def test_do_not_store_messages():
    session_id = "test-session-id"
    outputs = await run_single_component(
        ChatInput, inputs={"should_store_message": True}, run_input="hello", session_id=session_id
    )
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "hello"
    assert outputs["message"].session_id == session_id

    assert len(await aget_messages(session_id=session_id)) == 1

    session_id = "test-session-id-another"
    outputs = await run_single_component(
        ChatInput, inputs={"should_store_message": False}, run_input="hello", session_id=session_id
    )
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "hello"
    assert outputs["message"].session_id == session_id

    assert len(await aget_messages(session_id=session_id)) == 0
