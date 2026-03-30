"""TranslationFlow - Language Detection, Translation, and Intent Classification.

This flow translates user input to English and classifies intent as either
'generate_component' or 'question'.

Usage:
    from langflow.agentic.flows.translation_flow import get_graph
    graph = await get_graph(provider="OpenAI", model_name="gpt-4o-mini")
"""

from lfx.base.models.model_metadata import get_provider_param_mapping
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models import LanguageModelComponent
from lfx.graph import Graph

TRANSLATION_PROMPT = """You are a Language Detection, Translation, and Intent Classification \
Agent for Langflow Assistant.

Your responsibilities are:
1. Translate the input text to English (if not already in English)
2. Classify the user's intent

Intent Classification:
- "generate_component": User wants you to CREATE/BUILD/GENERATE/MODIFY a custom Langflow component.
  This includes both new component requests AND follow-up modifications to a previous component.
  Examples: "Create a component that calls an API", "Build me a custom component for...",
  "can you use dataframe output instead?", "add error handling", "make it also support CSV",
  "change the output to return a list", "use requests instead of urllib", "add a timeout parameter"
- "question": User is ASKING A QUESTION about Langflow, seeking help with Langflow, or wants \
information about Langflow features, components, flows, or how to use Langflow.
  Examples: "How do I create a component?", "What is a component?", "Can you explain flows?", \
"How to connect two components?"
- "off_topic": The question is NOT about Langflow. It is about other tools, platforms, general \
knowledge, or anything unrelated to Langflow.
  Examples: "How does n8n work?", "What is Python?", "Tell me about React", "How to cook pasta", \
"Explain Docker", "What is AutoGen?", "How does Make.com work?", "Write me a poem"

IMPORTANT rules:
- "How to create a component" = question (asking for Langflow guidance)
- "Create a component that does X" = generate_component (requesting creation)
- Short follow-up requests that imply changes to something previously generated = generate_component
  (e.g., "use X instead", "add Y", "change Z", "make it do W", "can you also...", "what about using...")
- Questions about OTHER tools or platforms (n8n, Make, Zapier, AutoGen, CrewAI, etc.) = off_topic
- General knowledge questions NOT related to Langflow = off_topic
- If unsure whether it's about Langflow, classify as "question" (not off_topic)

Output format (JSON only, no markdown):
{{"translation": "<english text>", "intent": "<generate_component|question|off_topic>"}}

Examples:
Input: "como criar um componente no langflow"
Output: {{"translation": "how to create a component in langflow", "intent": "question"}}

Input: "crie um componente que chama uma API"
Output: {{"translation": "create a component that calls an API", "intent": "generate_component"}}

Input: "what is the best way to build flows?"
Output: {{"translation": "what is the best way to build flows?", "intent": "question"}}

Input: "make me a component that parses JSON"
Output: {{"translation": "make me a component that parses JSON", "intent": "generate_component"}}

Input: "can you use dataframe output instead?"
Output: {{"translation": "can you use dataframe output instead?", "intent": "generate_component"}}

Input: "add a retry mechanism with exponential backoff"
Output: {{"translation": "add a retry mechanism with exponential backoff", "intent": "generate_component"}}

Input: "what does the output format look like?"
Output: {{"translation": "what does the output format look like?", "intent": "question"}}

Input: "como funciona o n8n?"
Output: {{"translation": "how does n8n work?", "intent": "off_topic"}}

Input: "explain how kubernetes works"
Output: {{"translation": "explain how kubernetes works", "intent": "off_topic"}}

Input: "write me a poem about cats"
Output: {{"translation": "write me a poem about cats", "intent": "off_topic"}}
"""


def _build_model_config(provider: str, model_name: str) -> list[dict]:
    """Build model configuration for LanguageModelComponent."""
    param_mapping = get_provider_param_mapping(provider)
    metadata: dict = {
        "api_key_param": param_mapping.get("api_key_param", "api_key"),
        "context_length": 128000,
        "model_class": param_mapping.get("model_class", "ChatOpenAI"),
        "model_name_param": param_mapping.get("model_name_param", "model"),
    }
    # Include extra params like base_url_param for providers like Ollama
    for extra_param in ("url_param", "project_id_param", "base_url_param"):
        if extra_param in param_mapping:
            metadata[extra_param] = param_mapping[extra_param]
    return [
        {
            "icon": provider,
            "metadata": metadata,
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
        should_store_message=False,
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
        should_store_message=False,
        clean_data=True,
        data_template="{text}",
    )

    return Graph(start=chat_input, end=chat_output)
