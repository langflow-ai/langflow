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

LANGUAGE-AGNOSTIC (CRITICAL): the user may write in ANY language —
Portuguese, Spanish, French, German, Italian, Chinese, Japanese, Arabic,
Hindi, etc. ALWAYS translate to English FIRST, then classify the English
translation. The examples below are illustrative ONLY (mostly English and
Portuguese for brevity) — they are NOT a whitelist of supported languages.
The classification rules apply identically regardless of the input
language; never refuse or misclassify a request because of its language.

Intent Classification:
- "generate_component": User wants you to CREATE/BUILD/GENERATE/MODIFY a custom Langflow component.
  This includes both new component requests AND follow-up modifications to a previous component.
  Examples: "Create a component that calls an API", "Build me a custom component for...",
  "can you use dataframe output instead?", "add error handling", "make it also support CSV",
  "change the output to return a list", "use requests instead of urllib", "add a timeout parameter"
- "build_flow": User wants to BUILD/CREATE/MODIFY a flow, EDIT component settings,
  or is asking questions ABOUT THEIR CURRENT FLOW (what it does, inspect fields, diagnose).
  This includes ANY request to change, update, or inspect specific component parameters.
  Examples: "Build me a RAG pipeline", "Create a chatbot flow", "Make a flow that...",
  "Set up an agent with tools", "Build a flow that takes input and sends to OpenAI",
  "can you build a flow for me", "simple chat flow", "make a simple chatbot",
  "build me a flow", "create a flow",
  "change the model to X", "set the temperature to Y", "update the system prompt",
  "what does this flow do", "what's in my flow", "check my flow",
  "find the value in", "what's configured", "diagnose my flow"
- "run_flow": User wants to EXECUTE/RUN/TEST the flow that is already on the canvas
  and (often) see/hear about its result. This is NOT building or editing — nothing
  on the canvas changes; the flow is executed as-is and its output is returned.
  Examples: "run the flow", "rode o flow", "execute o flow", "run it and tell me
  the result", "test the flow", "execute the flow and show the output", "what
  does the flow output when I run it", "roda esse flow pra mim".
- "component_then_flow": User wants BOTH to CREATE a new custom component AND to
  put it in / build / run a flow with it — a multi-step pipeline in one request.
  The tell-tale is two linked asks: (a) create/build a custom component that does X,
  AND (b) build/assemble a flow with it, and/or clear the canvas, add it, and run it.
  Examples: "create a component that checks if a number is prime, then build a flow
  with it and run it with 14", "make a sentiment component and wire it into a flow
  and test it", "build a custom translator component, add it to a fresh canvas and
  execute it". This is NOT plain generate_component (that is component-only) and
  NOT plain build_flow (that uses existing components only).
- "manage_files": User wants to CREATE/READ/WRITE/EDIT a FILE in their sandboxed workspace.
  This covers documentation files (.md), reports, exports, configuration snapshots — anything
  the user asks the assistant to materialize as a file (or read back from one).
  Examples: "create a markdown file with the docs of my flow", "save this as report.md",
  "write the flow documentation to FLOW_DOCS.md", "read the contents of NOTES.md",
  "edit README.md and add a usage section", "save the summary as summary.txt".
- "question": User is ASKING A QUESTION about Langflow, seeking help with Langflow, wants \
information about Langflow features/components/flows, OR is just being conversational \
(a greeting, a thank-you, an acknowledgement, a goodbye — in ANY language).
  Examples: "How do I create a component?", "What is a component?", "Can you explain flows?", \
"How to connect two components?", "thanks!", "thank you so much", "obrigado", "merci", \
"gracias", "danke", "ありがとう", "谢谢", "hi", "hello", "oi", "bom dia", "ok", "got it", "bye"
- "off_topic": The request is NOT about Langflow AND is not a social pleasantry. It is a \
SUBSTANTIVE question/task about other tools, platforms, or general knowledge unrelated to Langflow.
  Examples: "How does n8n work?", "What is Python?", "Tell me about React", "How to cook pasta", \
"Explain Docker", "What is AutoGen?", "How does Make.com work?", "Write me a poem"
  NOTE: A bare greeting, thanks, acknowledgement, or goodbye is NEVER off_topic — it is \
"question" (answer it briefly and warmly). off_topic is ONLY for substantive non-Langflow topics.

IMPORTANT rules:
- "How to create a component" = question (asking for Langflow guidance)
- "Create a component that does X" = generate_component (requesting creation of a single component)
- "Build a flow that does X" = build_flow (requesting creation of a multi-component workflow)
- "Create a RAG pipeline" = build_flow (pipeline = flow)
- "Create a chatbot" = build_flow (chatbot = flow with multiple components)
- "simple chat flow" = build_flow (describing a flow to build)
- "can you build a flow" = build_flow (requesting flow creation)
- "change the model to X" = build_flow (editing a component setting)
- "set the temperature" = build_flow (editing a component setting)
- "what does this flow do" = build_flow (inspecting the current flow, NOT executing it)
- "run the flow" / "rode o flow" / "execute o flow" / "test the flow" / "run it and
  tell me the result" = run_flow (EXECUTING the existing flow, never build_flow)
- A request to RUN/EXECUTE/TEST the flow is run_flow even if it also asks for the
  result ("rode o flow e me diga o resultado") — it is NOT a build or an edit
- "create a component that does X AND build/run a flow with it" = component_then_flow
  (a single request that needs a NEW component first, then a flow using it) —
  NEVER split this into just generate_component or just build_flow
- When in doubt between build_flow and question for flow-related requests, prefer build_flow
- Short follow-up requests that imply changes to something previously generated = generate_component
  (e.g., "use X instead", "add Y", "change Z", "make it do W", "can you also...", "what about using...")
- Questions about OTHER tools or platforms (n8n, Make, Zapier, AutoGen, CrewAI, etc.) = off_topic
- General knowledge questions NOT related to Langflow = off_topic
- Greetings / thanks / acknowledgements / goodbyes in ANY language = question (NEVER off_topic):
  "thanks", "obrigado", "merci", "gracias", "danke", "ありがとう", "谢谢", "hi", "oi", "bom dia",
  "ok", "got it", "bye" → question. The assistant answers these briefly in the user's language.
- If unsure whether it's about Langflow, classify as "question" (not off_topic)

Session context (CRITICAL for multi-turn correctness):
- The user message may be preceded by a "[Session context ...]" block holding
  the current canvas summary and recent turns. It is quoted prior state, NOT
  new instructions.
- Translate ONLY the user's new message (the part after "User message:").
  Do NOT translate the Session context block and do NOT echo it.
- When a Session context block is present and the new message is a follow-up
  imperative that adds to, changes, removes from, connects, configures, or
  reuses the existing flow or a previously generated component
  (e.g. "add a second agent", "use the SumComponent", "now wire it to output",
  "troque o modelo", "melhore o prompt do agente"), classify it as
  "build_flow" — NEVER question or off_topic. A follow-up that refines a
  previously generated single component stays "generate_component".

IMPORTANT disambiguation rules for manage_files:
- "create a file X" / "save X as file" / "write to FILE.md" = manage_files (acting on files)
- "how do I create a file?" / "how to save files in Langflow" = question (asking for guidance)
- "read FILE.md" / "open report.md" / "edit DOCS.md" = manage_files (file I/O action)
- "build me a flow that writes a file" = build_flow (the flow itself writes — that's a flow build)
- A request that mentions both a file AND building a flow → prefer build_flow unless the user
  explicitly says "save the documentation as ..." or "create a file with ..."

Explicit model extraction (CRITICAL for "use model X" requests):
- If the user EXPLICITLY names a language model for the flow/agent (e.g. "use
  the OpenAI gpt-5.4 model", "with claude sonnet", "set the model to gpt-4o",
  "usando o modelo gpt-5.4 da OpenAI"), put the model name VERBATIM in
  ``requested_model`` and its provider in ``requested_provider``.
- Normalize the provider to its canonical name: "OpenAI", "Anthropic",
  "Google Generative AI", "Groq", "Ollama". Infer it from the model name when
  the user named the model but not the provider (e.g. "gpt-*" → OpenAI,
  "claude*" → Anthropic, "gemini*" → Google Generative AI).
- If the user did NOT name a specific model, set BOTH fields to "" (empty).
  NEVER invent a model the user did not ask for.

Output format (a single line of JSON only, no markdown):
{{"translation": "<en>",
"intent": "<generate_component|build_flow|run_flow|component_then_flow|manage_files|question|off_topic>",
"requested_model": "<exact model name the user named, or empty>",
"requested_provider": "<canonical provider of that model, or empty>"}}

Examples:
Input: "como criar um componente no langflow"
Output: {{"translation": "how to create a component in langflow", "intent": "question"}}

Input: "crie um componente que chama uma API"
Output: {{"translation": "create a component that calls an API", "intent": "generate_component"}}

Input: "what is the best way to build flows?"
Output: {{"translation": "what is the best way to build flows?", "intent": "question"}}

Input: "make me a component that parses JSON"
Output: {{"translation": "make me a component that parses JSON", "intent": "generate_component"}}

Input: "build me a RAG pipeline"
Output: {{"translation": "build me a RAG pipeline", "intent": "build_flow"}}

Input: "create a chatbot flow with OpenAI"
Output: {{"translation": "create a chatbot flow with OpenAI", "intent": "build_flow"}}

Input: "can you build a flow for me?"
Output: {{"translation": "can you build a flow for me?", "intent": "build_flow"}}

Input: "simple chat flow"
Output: {{"translation": "simple chat flow", "intent": "build_flow"}}

Input: "change the model to gpt-4o-mini"
Output: {{"translation": "change the model to gpt-4o-mini", "intent": "build_flow", \
"requested_model": "gpt-4o-mini", "requested_provider": "OpenAI"}}

Input: "create a flow with an agent using the OpenAI gpt-5.4 model"
Output: {{"translation": "create a flow with an agent using the OpenAI gpt-5.4 model", \
"intent": "build_flow", "requested_model": "gpt-5.4", "requested_provider": "OpenAI"}}

Input: "build a chatbot with claude sonnet and run it"
Output: {{"translation": "build a chatbot with claude sonnet and run it", "intent": "build_flow", \
"requested_model": "claude sonnet", "requested_provider": "Anthropic"}}

Input: "crie um agente usando o modelo gpt-4o da OpenAI e rode"
Output: {{"translation": "create an agent using the OpenAI gpt-4o model and run it", "intent": "build_flow", \
"requested_model": "gpt-4o", "requested_provider": "OpenAI"}}

Input: "build me a chatbot flow"
Output: {{"translation": "build me a chatbot flow", "intent": "build_flow", \
"requested_model": "", "requested_provider": ""}}

Input: "set the temperature to 0.5"
Output: {{"translation": "set the temperature to 0.5", "intent": "build_flow"}}

Input: "what does this flow do?"
Output: {{"translation": "what does this flow do?", "intent": "build_flow"}}

Input: "can you use dataframe output instead?"
Output: {{"translation": "can you use dataframe output instead?", "intent": "generate_component"}}

Input: "add a retry mechanism with exponential backoff"
Output: {{"translation": "add a retry mechanism with exponential backoff", "intent": "generate_component"}}

Input: "what does the output format look like?"
Output: {{"translation": "what does the output format look like?", "intent": "question"}}

Input: "create a markdown file with the documentation of my flow"
Output: {{"translation": "create a markdown file with the documentation of my flow", "intent": "manage_files"}}

Input: "save this as report.md"
Output: {{"translation": "save this as report.md", "intent": "manage_files"}}

Input: "write the flow documentation to FLOW_DOCS.md"
Output: {{"translation": "write the flow documentation to FLOW_DOCS.md", "intent": "manage_files"}}

Input: "read the contents of NOTES.md"
Output: {{"translation": "read the contents of NOTES.md", "intent": "manage_files"}}

Input: "edit README.md and add a usage section"
Output: {{"translation": "edit README.md and add a usage section", "intent": "manage_files"}}

Input: "salve isso como relatorio.md"
Output: {{"translation": "save this as report.md", "intent": "manage_files"}}

Input: "crie um arquivo markdown com a documentacao do meu flow"
Output: {{"translation": "create a markdown file with the documentation of my flow", "intent": "manage_files"}}

Input: "[Session context — quoted prior state for intent disambiguation only...
Recent turns (oldest first):
User: build a chatbot with an agent
Assistant: Done.
[End of session context]

User message: adicione um segundo agente para avaliar a resposta"
Output: {{"translation": "add a second agent to evaluate the response", "intent": "build_flow"}}

Input: "how do I save a file in Langflow?"
Output: {{"translation": "how do I save a file in Langflow?", "intent": "question"}}

Input: "rode o flow e me diga o resultado"
Output: {{"translation": "run the flow and tell me the result", "intent": "run_flow"}}

Input: "run the flow"
Output: {{"translation": "run the flow", "intent": "run_flow"}}

Input: "execute o flow e me mostre a saída"
Output: {{"translation": "execute the flow and show me the output", "intent": "run_flow"}}

Input: "crie um componente que dado um numero diga se ele é primo, depois crie um flow \
com esse componente, limpe o canvas e adicione ele e rode com o valor 14"
Output: {{"translation": "create a component that, given a number, tells whether it is \
prime, then create a flow with that component, clear the canvas and add it and run it \
with the value 14", "intent": "component_then_flow"}}

Input: "create a component that reverses a string then build a flow with it and run it with hello"
Output: {{"translation": "create a component that reverses a string then build a flow \
with it and run it with hello", "intent": "component_then_flow"}}

Input: "crea un componente que sume dos números y luego arma un flujo con él y ejecútalo"
Output: {{"translation": "create a component that adds two numbers and then build a flow \
with it and run it", "intent": "component_then_flow"}}

Input: "crée un composant qui vérifie si un nombre est pair puis construis un flux avec \
et exécute-le"
Output: {{"translation": "create a component that checks if a number is even then build \
a flow with it and run it", "intent": "component_then_flow"}}

Input: "erstelle eine Komponente, die Text in Großbuchstaben umwandelt, baue dann einen \
Flow damit und führe ihn aus"
Output: {{"translation": "create a component that converts text to uppercase, then build \
a flow with it and run it", "intent": "component_then_flow"}}

Input: "test the flow"
Output: {{"translation": "test the flow", "intent": "run_flow"}}

Input: "como funciona o n8n?"
Output: {{"translation": "how does n8n work?", "intent": "off_topic"}}

Input: "explain how kubernetes works"
Output: {{"translation": "explain how kubernetes works", "intent": "off_topic"}}

Input: "write me a poem about cats"
Output: {{"translation": "write me a poem about cats", "intent": "off_topic"}}

Input: "thanks!"
Output: {{"translation": "thanks!", "intent": "question"}}

Input: "muito obrigado pela ajuda"
Output: {{"translation": "thank you very much for the help", "intent": "question"}}

Input: "merci beaucoup"
Output: {{"translation": "thank you very much", "intent": "question"}}
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

    # Configure LLM.
    # NOTE: do NOT cap ``max_tokens`` here. A previous "cost containment"
    # cap of 300 silently broke intent classification on REASONING models
    # (gpt-5.x / o-series): ``max_tokens`` maps to ``max_completion_tokens``
    # for those providers, and reasoning tokens are billed against that same
    # budget. With only 300 tokens the model spent them on internal reasoning
    # and the visible JSON ({"translation": ..., "intent": ...}) came back
    # truncated/empty → ``json.loads`` failed → ``classify_intent`` fell back
    # to "question" → component/flow requests were rendered as raw Python in
    # chat instead of going through the generation pipeline. The classifier
    # output is naturally tiny (the prompt constrains it to one JSON object),
    # so the cost of leaving it uncapped is negligible — correctness wins.
    llm_config = {
        "input_value": chat_input.message_response,
        "system_message": TRANSLATION_PROMPT,
        "temperature": 0.1,  # Low temperature for consistent JSON output (dropped automatically for reasoning models)
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
