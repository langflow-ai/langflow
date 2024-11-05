from langchain_core.prompts.chat import ChatPromptTemplate
from langflow.schema.message import Message


def test_message_prompt_serialization():
    template = "Hello, {name}!"
    message = Message.from_template_and_variables(template, name="Langflow")
    assert message.text == "Hello, Langflow!"

    prompt = message.load_lc_prompt()
    assert isinstance(prompt, ChatPromptTemplate)
    assert prompt.messages[0].content == "Hello, Langflow!"
