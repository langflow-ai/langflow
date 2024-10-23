from textwrap import dedent

from langflow.components.data import URLComponent
from langflow.components.helpers import ParseDataComponent
from langflow.components.inputs import TextInputComponent
from langflow.components.models import OpenAIModelComponent
from langflow.components.outputs import ChatOutput
from langflow.components.prompts import PromptComponent
from langflow.graph import Graph


def blog_writer_graph(template: str | None = None):
    if template is None:
        template = dedent("""Reference 1:

{references}

---

{instructions}

Blog:
""")
    url_component = URLComponent()
    url_component.set(urls=["https://langflow.org/", "https://docs.langflow.org/"])
    parse_data_component = ParseDataComponent()
    parse_data_component.set(data=url_component.fetch_content)

    text_input = TextInputComponent(_display_name="Instructions")
    text_input.set(
        input_value="Use the references above for style to write a new blog/tutorial about Langflow and AI. "
        "Suggest non-covered topics."
    )

    prompt_component = PromptComponent()
    prompt_component.set(
        template=template,
        instructions=text_input.text_response,
        references=parse_data_component.parse_data,
    )

    openai_component = OpenAIModelComponent()
    openai_component.set(input_value=prompt_component.build_prompt)

    chat_output = ChatOutput()
    chat_output.set(input_value=openai_component.text_response)

    return Graph(start=text_input, end=chat_output)
