"""Generate concise descriptions from server-provided Langflow context."""

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models import LanguageModelComponent
from lfx.graph import Graph

from langflow.agentic.flows.model_config import build_model_config

SYSTEM_PROMPT = """You write concise, accurate descriptions for Langflow workflows and components.
Use the supplied JSON context as the source of truth. Explain the purpose and important behavior,
not implementation trivia. Return only the description, with no heading, quotes, or commentary.
The user input includes an output language locale. You MUST write in that locale's language,
regardless of the language used by existing descriptions or JSON context. Keep the result under
250 characters for a workflow and under 1000 characters for a component."""


def get_graph(
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> Graph:
    """Build the description-generation graph."""
    provider = provider or "OpenAI"
    model_name = model_name or "gpt-4o-mini"

    chat_input = ChatInput().set(sender="User", sender_name="User", should_store_message=False)
    llm = LanguageModelComponent()
    llm.set_input_value("model", build_model_config(provider, model_name))
    llm_config = {
        "input_value": chat_input.message_response,
        "system_message": SYSTEM_PROMPT,
        "temperature": 0.2,
    }
    if api_key_var:
        llm_config["api_key"] = api_key_var
    llm.set(**llm_config)

    chat_output = ChatOutput().set(
        input_value=llm.text_response,
        sender="Machine",
        sender_name="AI",
        should_store_message=False,
        clean_data=True,
        data_template="{text}",
    )
    return Graph(start=chat_input, end=chat_output)
