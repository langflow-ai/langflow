"""TranslationFlow - Language Detection, Translation, and Intent Classification.

This flow translates user input to English and classifies intent as either
'generate_component', 'generate_flow', 'question', or 'off_topic'.

Usage:
    from langflow.agentic.flows.translation_flow import get_graph
    graph = await get_graph(provider="OpenAI", model_name="gpt-4o-mini")
"""

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models import LanguageModelComponent
from lfx.graph import Graph

from langflow.agentic.flows._model_config import build_model_config

TRANSLATION_PROMPT = """You are a Language Detection, Translation, and Intent Classification \
Agent for Langflow Assistant.

Your responsibilities are:
1. Translate the input text to English (if not already in English)
2. Classify the user's intent

Intent Classification:
- "generate_component": User wants you to CREATE/BUILD/GENERATE/MODIFY a single custom Langflow \
component (a Python class). This includes new component requests AND follow-up modifications to a \
previous component.
  Examples: "Create a component that calls an API", "Build me a custom component for...",
  "can you use dataframe output instead?", "add error handling", "make it also support CSV",
  "change the output to return a list", "use requests instead of urllib", "add a timeout parameter"
- "generate_flow": User wants to CREATE/BUILD a complete FLOW or PIPELINE with multiple existing \
Langflow components connected together. They describe a workflow, not a single custom component.
  Examples: "build a RAG pipeline with OpenAI and Milvus", "create a chatbot flow with GPT-4",
  "make a flow that takes user input and generates embeddings",
  "connect ChatInput to an LLM to ChatOutput", "add a vector store retrieval step before the LLM",
  "replace the OpenAI model with Claude in my flow", "wire up a summarization pipeline"
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
- "Create a component that does X" = generate_component (single custom Python class)
- "Build a flow/pipeline that does X" = generate_flow (multiple connected components)
- "Connect X to Y" or "wire up X with Y" = generate_flow ONLY when phrased as an imperative command
- "How do I connect X to Y?" or "Can I wire X to Y?" = question (interrogative, not a build request)
- Keywords: pipeline/flow/chain/workflow/connect/wire = generate_flow when used imperatively
- Keywords: component/class/custom/code = generate_component
- Short follow-up requests implying changes to a previously generated component = generate_component
  (e.g., "use X instead", "add Y", "change Z", "make it do W")
- Short follow-up requests implying changes to a flow = generate_flow
  (e.g., "replace OpenAI with Claude", "add a memory step", "remove the vector store")
- If ambiguous between component and flow, prefer generate_flow (more capable)
- Questions about OTHER tools or platforms (n8n, Make, Zapier, AutoGen, CrewAI, etc.) = off_topic
- General knowledge questions NOT related to Langflow = off_topic
- If unsure whether it's about Langflow, classify as "question" (not off_topic)

Output format (JSON only, no markdown):
{{"translation": "<english text>", "intent": "<generate_component|generate_flow|question|off_topic>"}}

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

Input: "build me a RAG pipeline with OpenAI and Milvus"
Output: {{"translation": "build me a RAG pipeline with OpenAI and Milvus", "intent": "generate_flow"}}

Input: "create a chatbot flow with input, GPT-4, and output"
Output: {{"translation": "create a chatbot flow with input, GPT-4, and output", "intent": "generate_flow"}}

Input: "replace the OpenAI model with Claude in my flow"
Output: {{"translation": "replace the OpenAI model with Claude in my flow", "intent": "generate_flow"}}
"""


# Keep the private alias for backward compatibility within this module
_build_model_config = build_model_config


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
