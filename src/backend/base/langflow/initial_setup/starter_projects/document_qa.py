from langflow.components.data.File import FileComponent
from langflow.components.helpers.ParseData import ParseDataComponent
from langflow.components.inputs.ChatInput import ChatInput
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.prompts.Prompt import PromptComponent
from langflow.graph.graph.base import Graph


def document_qa_graph(template: str | None = None):
    if template is None:
        template = """Answer user's questions based on the document below:

---

{Document}

---

Question:
{Question}

Answer:
"""
    file_component = FileComponent()
    parse_data_component = ParseDataComponent()
    parse_data_component.set(data=file_component.load_file)

    chat_input = ChatInput()
    prompt_component = PromptComponent()
    prompt_component.set(
        template=template,
        context=parse_data_component.parse_data,
        question=chat_input.message_response,
    )

    openai_component = OpenAIModelComponent()
    openai_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput()
    chat_output.set(input_value=openai_component.text_response)

    graph = Graph(start=chat_input, end=chat_output)
    return graph
