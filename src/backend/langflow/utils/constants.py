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
    "claude-instant-v1-100k",  # An enhanced version of claude-instant-v1 with a 100,000 token context window that retains its performance.
    # Specific sub-versions of the above models:
    "claude-v1.3",  # Compared to claude-v1.2, it's more robust against red-team inputs, better at precise instruction-following, better at code, and better and non-English dialogue and writing.
    "claude-v1.3-100k",  # An enhanced version of claude-v1.3 with a 100,000 token (roughly 75,000 word) context window.
    "claude-v1.2",  # An improved version of claude-v1. It is slightly improved at general helpfulness, instruction following, coding, and other tasks. It is also considerably better with non-English languages. This model also has the ability to role play (in harmless ways) more consistently, and it defaults to writing somewhat longer and more thorough responses.
    "claude-v1.0",  # An earlier version of claude-v1.
    "claude-instant-v1.1",  # latest version of claude-instant-v1. It is better than claude-instant-v1.0 at a wide variety of tasks including writing, coding, and instruction following.
    "claude-instant-v1.1-100k",  # An enhanced version of claude-instant-v1.1 with a 100,000 token context window that retains its lightning fast 40 word/sec performance.
    "claude-instant-v1.0",  # An earlier version of claude-instant-v1.
]

DEFAULT_PYTHON_FUNCTION = """
def python_function(text: str) -> str:
    \"\"\"This is a default python function that returns the input text\"\"\"
    return text
"""
