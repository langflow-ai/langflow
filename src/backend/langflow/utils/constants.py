OPENAI_MODELS = [
    "text-davinci-003",
    "text-davinci-002",
    "text-curie-001",
    "text-babbage-001",
    "text-ada-001",
]
CHAT_OPENAI_MODELS = ["gpt-3.5-turbo", "gpt-4", "gpt-4-32k"]

ANTHROPIC_MODELS = [
    "claude-v1",  # largest model, ideal for a wide range of more complex tasks.
    "claude-v1-100k",  # An enhanced version of claude-v1 with a 100,000 token (roughly 75,000 word) context window.
    "claude-instant-v1",  # A smaller model with far lower latency, sampling at roughly 40 words/sec!
    "claude-instant-v1-100k",  # Like claude-instant-v1 with a 100,000 token context window but retains its performance.
    # Specific sub-versions of the above models:
    "claude-v1.3",  # Vs claude-v1.2: better instruction-following, code, and non-English dialogue and writing.
    "claude-v1.3-100k",  # An enhanced version of claude-v1.3 with a 100,000 token (roughly 75,000 word) context window.
    "claude-v1.2",  # Vs claude-v1.1: small adv in general helpfulness, instruction following, coding, and other tasks.
    "claude-v1.0",  # An earlier version of claude-v1.
    "claude-instant-v1.1",  # Latest version of claude-instant-v1. Better than claude-instant-v1.0 at most tasks.
    "claude-instant-v1.1-100k",  # Version of claude-instant-v1.1 with a 100K token context window.
    "claude-instant-v1.0",  # An earlier version of claude-instant-v1.
]

DEFAULT_PYTHON_FUNCTION = """
def python_function(text: str) -> str:
    \"\"\"This is a default python function that returns the input text\"\"\"
    return text
"""
