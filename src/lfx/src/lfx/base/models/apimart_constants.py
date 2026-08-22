"""APIMart text-generation model catalog primitives.

The list mirrors the public ``chat`` catalog on https://apimart.ai/pricing.
Entries that require a non-chat endpoint (embeddings, moderation, transcription,
realtime, OCR, or legacy completions) are intentionally excluded because the
APIMart provider is instantiated through LangChain's ``ChatOpenAI`` class.
"""

from .model_metadata import create_model_metadata

APIMART_DEFAULT_MODEL = "gpt-5.5"

# Keep the default first so a newly configured provider selects it naturally.
# The remaining names retain the order published by APIMart's chat catalog.
APIMART_TEXT_MODEL_NAMES: list[str] = list(
    filter(
        None,
        """
gpt-5.5
gpt-3.5-turbo
gpt-4o
gpt-4o-mini
chatgpt-4o-latest
claude-fable-5
claude-haiku-4-5-20251001
claude-haiku-4-5-20251001-thinking
claude-opus-4-5-20251101
claude-opus-4-5-20251101-thinking
claude-opus-4-6
claude-opus-4-6-thinking
claude-opus-4-7
claude-opus-4-8
claude-sonnet-4-5-20250929
claude-sonnet-4-5-20250929-thinking
claude-sonnet-4-6
claude-sonnet-4-6-thinking
claude-sonnet-5
deepseek-r1
deepseek-r1-0528
deepseek-r1-250528
deepseek-v3
deepseek-v3-0324
deepseek-v3.1-terminus
deepseek-v3.2
deepseek-v3.2-exp
deepseek-v3.2-think
deepseek-v4-flash
deepseek-v4-pro
gemini-2.0-flash
gemini-2.5-flash
gemini-2.5-flash-lite
gemini-2.5-flash-nothinking
gemini-2.5-flash-thinking
gemini-2.5-pro
gemini-2.5-pro-nothinking
gemini-2.5-pro-thinking
gemini-3-flash-preview
gemini-3-flash-preview-nothinking
gemini-3-flash-preview-thinking
gemini-3-pro-preview
gemini-3-pro-preview-thinking
gemini-3.1-flash-lite-preview
gemini-3.1-pro-preview
gemini-3.1-pro-preview-thinking
gemini-3.5-flash
glm-4.6
glm-4.7
glm-5
glm-5.1
glm-5.2
gpt-3.5-turbo-0125
gpt-3.5-turbo-0613
gpt-3.5-turbo-1106
gpt-3.5-turbo-16k
gpt-3.5-turbo-16k-0613
gpt-4-0125-preview
gpt-4-1106-preview
gpt-4-32k
gpt-4-32k-0613
gpt-4-vision-preview
gpt-4.1
gpt-4.1-2025-04-14
gpt-4.1-mini
gpt-4.1-mini-2025-04-14
gpt-4.1-nano
gpt-4.1-nano-2025-04-14
gpt-4.5-preview
gpt-4.5-preview-2025-02-27
gpt-4o-2024-05-13
gpt-4o-2024-11-20
gpt-5
gpt-5-2025-08-07
gpt-5-chat-latest
gpt-5-codex
gpt-5-mini
gpt-5-mini-2025-08-07
gpt-5-nano
gpt-5-nano-2025-08-07
gpt-5-pro
gpt-5-pro-2025-10-06
gpt-5-search-api
gpt-5-search-api-2025-10-14
gpt-5.1
gpt-5.1-2025-11-13
gpt-5.1-chat-latest
gpt-5.1-codex
gpt-5.1-codex-max
gpt-5.1-codex-mini
gpt-5.2
gpt-5.2-chat-latest
gpt-5.2-codex
gpt-5.2-pro
gpt-5.3-codex
gpt-5.4
gpt-5.4-mini
gpt-5.4-nano
gpt-5.4-pro
gpt-5.6-luna
gpt-5.6-sol
gpt-5.6-terra
grok-4.20-0309-non-reasoning
grok-4.20-0309-reasoning
grok-4.20-multi-agent-0309
grok-4.3
grok-4.5
grok-build-0.1
kimi-k2-instruct
kimi-k2-thinking
kimi-k2.5
kimi-k2.6
kimi-k2.7-code
kimi-k2.7-code-highspeed
mimo-v2.5-pro
minimax-m2.1
minimax-m2.5
minimax-m2.7
minimax-m3
o1
o1-2024-12-17
o1-mini
o1-mini-2024-09-12
o1-preview
o1-preview-2024-09-12
o1-pro
o1-pro-2025-03-19
o3
o3-2025-04-16
o3-deep-research
o3-deep-research-2025-06-26
o3-mini
o3-mini-2025-01-31
o3-mini-2025-01-31-high
o3-mini-2025-01-31-low
o3-mini-2025-01-31-medium
o3-mini-high
o3-mini-low
o3-mini-medium
o3-pro
o3-pro-2025-06-10
o4-mini
o4-mini-2025-04-16
o4-mini-deep-research
o4-mini-deep-research-2025-06-26
qwen-turbo
qwen3.6-flash
qwen3.6-plus
qwen3.7-max
qwen3.7-plus
step-3.7-flash
""".splitlines(),
    )
)


def _icon_for_model(model_name: str) -> str:
    if model_name.startswith("claude-"):
        return "Anthropic"
    if model_name.startswith("deepseek-"):
        return "DeepSeek"
    if model_name.startswith("gemini-"):
        return "GoogleGenerativeAI"
    if model_name.startswith("grok-"):
        return "xAI"
    return "OpenAI"


def _is_reasoning_model(model_name: str) -> bool:
    return (
        model_name.startswith(("gpt-5", "o1", "o3", "o4", "deepseek-r1"))
        or "thinking" in model_name
        or "think" in model_name
        or "reasoning" in model_name
    )


def _is_search_model(model_name: str) -> bool:
    return "search-api" in model_name or "deep-research" in model_name


APIMART_MODELS_DETAILED = [
    create_model_metadata(
        provider="APIMart",
        name=model_name,
        icon=_icon_for_model(model_name),
        tool_calling=True,
        reasoning=_is_reasoning_model(model_name),
        search=_is_search_model(model_name),
        preview="preview" in model_name or model_name.endswith("-exp"),
        default=model_name == APIMART_DEFAULT_MODEL,
    )
    for model_name in APIMART_TEXT_MODEL_NAMES
]
