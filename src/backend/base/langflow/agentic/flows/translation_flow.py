"""TranslationFlow - Language Detection, Translation, and Intent Classification.

This flow translates user input to English and classifies intent as either
'generate_component' or 'question'.

Usage:
    from langflow.agentic.flows.translation_flow import get_graph
    graph = await get_graph(provider="OpenAI", model_name="gpt-4o-mini")
"""

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models import LanguageModelComponent
from lfx.graph import Graph

TRANSLATION_PROMPT = """You are a Language Detection, Translation, and Intent Classification \
Agent for Langflow Assistant.

Your responsibilities are:
1. Translate the input text to English (if not already in English)
2. Classify the user's intent

Intent Classification:
- "generate_component": User wants you to CREATE/BUILD/GENERATE a custom Langflow component for them
  Examples: "Create a component that calls an API", "Build me a custom component for...", "Generate a component to..."
- "question": User is ASKING A QUESTION, seeking help, or wants information
  Examples: "How do I create a component?", "What is a component?", "Can you explain...", "How to use..."

IMPORTANT: Distinguish between:
- "How to create a component" = question (asking for guidance)
- "Create a component that does X" = generate_component (requesting creation)

Output format (JSON only, no markdown):
{{"translation": "<english text>", "intent": "<generate_component|question>"}}

Examples:
Input: "como criar um componente no langflow"
Output: {{"translation": "how to create a component in langflow", "intent": "question"}}

Input: "crie um componente que chama uma API"
Output: {{"translation": "create a component that calls an API", "intent": "generate_component"}}

Input: "what is the best way to build flows?"
Output: {{"translation": "what is the best way to build flows?", "intent": "question"}}

Input: "make me a component that parses JSON"
Output: {{"translation": "make me a component that parses JSON", "intent": "generate_component"}}
"""


def _build_model_config(provider: str, model_name: str) -> list[dict]:
    """Build model configuration for LanguageModelComponent."""
    model_classes = {
        "OpenAI": "ChatOpenAI",
        "Anthropic": "ChatAnthropic",
        "Google Generative AI": "ChatGoogleGenerativeAI",
        "Groq": "ChatGroq",
        "Azure OpenAI": "AzureChatOpenAI",
    }
    return [
        {
            "icon": provider,
            "metadata": {
                "api_key_param": "api_key",
                "context_length": 128000,
                "model_class": model_classes.get(provider, "ChatOpenAI"),
                "model_name_param": "model",
            },
            "name": model_name,
            "provider": provider,
        }
    ]


def get_graph(
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> Graph:
    """Create and return the TranslationFlow graph.

    Args:
        provider: Model provider (e.g., "OpenAI", "Anthropic"). Defaults to OpenAI.
        model_name: Model name (e.g., "gpt-4o-mini"). Defaults to gpt-4o-mini.
        api_key_var: Optional API key variable name (e.g., "OPENAI_API_KEY").

    Returns:
        Graph: The configured translation flow graph.
    """
    # Use defaults if not provided
    provider = provider or "OpenAI"
    model_name = model_name or "gpt-4o-mini"

    # Create chat input component
    chat_input = ChatInput()
    chat_input.set(
        sender="User",
        sender_name="User",
        should_store_message=True,
    )

    # Create language model component
    llm = LanguageModelComponent()

    # Set model configuration
    llm.set_input_value("model", _build_model_config(provider, model_name))

    # Configure LLM
    llm_config = {
        "input_value": chat_input.message_response,
        "system_message": TRANSLATION_PROMPT,
        "temperature": 0.1,  # Low temperature for consistent JSON output
    }

    if api_key_var:
        llm_config["api_key"] = api_key_var

    llm.set(**llm_config)

    # Create chat output component
    chat_output = ChatOutput()
    chat_output.set(
        input_value=llm.text_response,
        sender="Machine",
        sender_name="AI",
        should_store_message=True,
        clean_data=True,
        data_template="{text}",
    )

    return Graph(start=chat_input, end=chat_output)
