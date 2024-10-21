import pytest
from langchain_core.prompts.chat import ChatPromptTemplate
from langflow.schema.message import Message


@pytest.mark.asyncio
async def test_message_async_prompt_serialization():
    template = "Hello, {name}!"
    message = await Message.from_template_and_variables(template, name="Langflow")
    assert message.text == "Hello, Langflow!"

    prompt = message.load_lc_prompt()
    assert isinstance(prompt, ChatPromptTemplate)
    assert prompt.messages[0].content == "Hello, Langflow!"


def test_message_prompt_serialization():
    template = "Hello, {name}!"
    message = Message.sync_from_template_and_variables(template, name="Langflow")
    assert message.text == "Hello, Langflow!"

    prompt = message.load_lc_prompt()
    assert isinstance(prompt, ChatPromptTemplate)
    assert prompt.messages[0].content == "Hello, Langflow!"
