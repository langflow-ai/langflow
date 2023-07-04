OPENAI_MODELS = [
    "text-davinci-003",
    "text-davinci-002",
    "text-curie-001",
    "text-babbage-001",
    "text-ada-001",
]
CHAT_OPENAI_MODELS = [
    "gpt-3.5-turbo-0613",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k-0613",
    "gpt-3.5-turbo-16k",
    "gpt-4-0613",
    "gpt-4-32k-0613",
    "gpt-4",
    "gpt-4-32k",
]

ANTHROPIC_MODELS = [
    # largest model, ideal for a wide range of more complex tasks.
    "claude-v1",
    # An enhanced version of claude-v1 with a 100,000 token (roughly 75,000 word) context window.
    "claude-v1-100k",
    # A smaller model with far lower latency, sampling at roughly 40 words/sec!
    "claude-instant-v1",
    # Like claude-instant-v1 with a 100,000 token context window but retains its performance.
    "claude-instant-v1-100k",

    # Specific sub-versions of the above models:
    # Vs claude-v1.2: better instruction-following, code, and non-English dialogue and writing.
    "claude-v1.3",
    # An enhanced version of claude-v1.3 with a 100,000 token (roughly 75,000 word) context window.
    "claude-v1.3-100k",
    # Vs claude-v1.1: small adv in general helpfulness, instruction following, coding, and other tasks.
    "claude-v1.2",
    # An earlier version of claude-v1.
    "claude-v1.0",
    # Latest version of claude-instant-v1. Better than claude-instant-v1.0 at most tasks.
    "claude-instant-v1.1",
    # Version of claude-instant-v1.1 with a 100K token context window.
    "claude-instant-v1.1-100k",
    # An earlier version of claude-instant-v1.
    "claude-instant-v1.0",
]

DEFAULT_PYTHON_FUNCTION = """
def python_function(text: str) -> str:
    \"\"\"This is a default python function that returns the input text\"\"\"
    return text
"""

DEFAULT_CUSTOM_COMPONENT_CODE = """
from langchain.chains import ConversationChain


class MyPythonClass:
    def __init__(self, name: str, year: int):
        self.name = name
        self.year = year

    def get_details(self):
        return f"Name: {self.name}, Year: {self.year}"

    def build(self, name: str, year: int, true_or_false: bool, no_type) -> ConversationChain:
        # do something...
        return ConversationChain()
"""

DIRECT_TYPES = ["str", "bool", "code", "int", "float", "Any", "prompt"]
