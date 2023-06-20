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

CTRANSFORMERS_DEFAULT_CONFIG = {
    "top_k": 40,
    "top_p": 0.95,
    "temperature": 0.8,
    "repetition_penalty": 1.1,
    "last_n_tokens": 64,
    "seed": -1,
    "max_new_tokens": 256,
    "stop": None,
    "stream": False,
    "reset": True,
    "batch_size": 8,
    "threads": -1,
    "context_length": -1,
    "gpu_layers": 0,
}
