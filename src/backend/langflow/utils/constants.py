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
from langflow.interface.chains.base import ChainCreator
from langflow.interface.tools.base import ToolCreator
from xyz.abc import MyClassA, MyClassB


class MyPythonClass(MyClassA, MyClassB):
    def __init__(self, title: str, author: str, year_published: int):
        self.title = title
        self.author = author
        self.year_published = year_published

    def get_details(self):
        return f"Title: {self.title}, Author: {self.author}, Year Published: {self.year_published}"

    def update_year_published(self, new_year: int):
        self.year_published = new_year
        print(f"The year of publication has been updated to {new_year}.")

    def build(self, name: str, my_int: int, my_str: str, my_bool: bool, no_type) -> ConversationChain:
        # do something...

        return ConversationChain()
"""

DIRECT_TYPES = ["str", "bool", "code", "int", "float", "Any", "prompt"]
