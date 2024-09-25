import pytest

from langflow import components
from langflow.code_gen.component import generate_instantiation_string, generate_script
from langflow.code_gen.generic import generate_import_statement


@pytest.fixture
def client():
    pass


def test_generate_script():
    chat_input = components.inputs.ChatInput(_id="chatInput-1230")
    text_output = components.outputs.TextOutput.TextOutputComponent(_id="textoutput-1231")
    text_output.set(input_value=chat_input.message_response)
    script = generate_script(instances=(chat_input, text_output), entry=chat_input, exit=text_output)
    assert (
        script
        == """from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs.TextOutput import TextOutputComponent

chatinput_1230 = ChatInput(_id='chatInput-1230')
textoutput_1231 = TextOutputComponent(_id='textoutput-1231')

textoutput_1231.set(input_value=chatinput_1230.message_response)

graph = Graph(entry=chatinput_1230, exit=textoutput_1231)"""
    )


def test_generate_import_statement_and_instantiation_string():
    chat_input_instance = components.inputs.ChatInput(_id="chatInput-1230")
    import_statement = generate_import_statement(chat_input_instance)
    instantiation_string = generate_instantiation_string(chat_input_instance)
    assert import_statement == "from langflow.components.inputs.ChatInput import ChatInput"
    assert instantiation_string == "chatinput_1230 = ChatInput(_id='chatInput-1230')"
