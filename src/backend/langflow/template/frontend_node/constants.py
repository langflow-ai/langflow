FORCE_SHOW_FIELDS = [
    "allowed_tools",
    "memory",
    "prefix",
    "examples",
    "temperature",
    "model_name",
    "headers",
    "max_value_length",
    "max_tokens",
]

DEFAULT_PROMPT = """
I want you to act as a naming consultant for new companies.

Here are some examples of good company names:

- search engine, Google
- social media, Facebook
- video sharing, YouTube

The name should be short, catchy and easy to remember.

What is a good name for a company that makes {product}?
"""

SYSTEM_PROMPT = """
You are a helpful assistant that talks casually about life in general.
You are a good listener and you can talk about anything.
"""

HUMAN_PROMPT = "{input}"

QA_CHAIN_TYPES = ["stuff", "map_reduce", "map_rerank", "refine"]


# This variable is used to tell the user
# that it can be changed to use other APIs
# like Prem and LocalAI
OPENAI_API_BASE_INFO = """
The base URL of the OpenAI API. Defaults to https://api.openai.com/v1.

You can change this to use other APIs like JinaChat, LocalAI and Prem.
"""
