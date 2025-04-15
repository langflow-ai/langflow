OPENAI_MODEL_NAMES = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4.5-preview",
    "gpt-4-turbo",
    "gpt-4-turbo-preview",
    "gpt-4",
    "gpt-3.5-turbo",
]

OPENAI_REASONING_MODEL_NAMES = [
    "o1",  # High-intelligence reasoning model
]
OPENAI_SEARCH_MODEL_NAMES = [
    "gpt-4o-mini-search-preview",
    "gpt-4o-search-preview",
]


NOT_SUPPORTED_MODELS = [
    "computer-use-preview",
    "gpt-4o-audio-preview",
    "gpt-4o-realtime-preview",
    "gpt-4o-mini-audio-preview",
    "gpt-4o-mini-realtime-preview",
    "o3-mini",
    "o1-mini",
]

OPENAI_EMBEDDING_MODEL_NAMES = [
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
]

# Backwards compatibility
MODEL_NAMES = OPENAI_MODEL_NAMES
