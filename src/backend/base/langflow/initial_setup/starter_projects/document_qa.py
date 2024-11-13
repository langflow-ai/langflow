from langflow.components.data import FileComponent
from langflow.components.inputs import ChatInput
from langflow.components.models import OpenAIModelComponent
from langflow.components.outputs import ChatOutput
from langflow.components.processing import ParseDataComponent
from langflow.components.prompts import PromptComponent
from langflow.graph import Graph


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

    return Graph(start=chat_input, end=chat_output)
