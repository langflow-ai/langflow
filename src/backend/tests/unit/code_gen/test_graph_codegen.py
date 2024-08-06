from langflow import components
from langflow.code_gen.graph import generate_script_from_graph
from langflow.graph.graph.base import Graph


def test_gerenate_script_from_graph():
    chat_input = components.inputs.ChatInput(_id="chatInput-1230")
    text_output = components.outputs.TextOutput.TextOutputComponent(_id="textoutput-1231")
    text_output.set(input_value=chat_input.message_response)
    chat_output = components.outputs.ChatOutput(input_value="test", _id="chatOutput-1232")
    chat_output.set(input_value=text_output.text_response)

    graph = Graph(chat_input, chat_output)
    script = generate_script_from_graph(graph)
    assert (
        script
        == """from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.outputs.TextOutput import TextOutputComponent

chatinput_1230 = ChatInput(_id='chatInput-1230')
textoutput_1231 = TextOutputComponent(_id='textoutput-1231')
chatoutput_1232 = ChatOutput(_id='chatOutput-1232')

textoutput_1231(input_value=chatinput_1230.message_response)
chatoutput_1232(input_value=textoutput_1231.text_response)"""
    )
