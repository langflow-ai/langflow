from typing import Any, Dict, List

OPENAI_MODELS = [
    "text-davinci-003",
    "text-davinci-002",
    "text-curie-001",
    "text-babbage-001",
    "text-ada-001",
]
CHAT_OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4-turbo-preview",
    "gpt-4-0125-preview",
    "gpt-4-1106-preview",
    "gpt-4-vision-preview",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-1106",
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


PYTHON_BASIC_TYPES = [str, bool, int, float, tuple, list, dict, set]
DIRECT_TYPES = [
    "str",
    "bool",
    "dict",
    "int",
    "float",
    "Any",
    "prompt",
    "code",
    "NestedDict",
]


LOADERS_INFO: List[Dict[str, Any]] = [
    {
        "loader": "AirbyteJSONLoader",
        "name": "Airbyte JSON (.jsonl)",
        "import": "langchain_community.document_loaders.AirbyteJSONLoader",
        "defaultFor": ["jsonl"],
        "allowdTypes": ["jsonl"],
    },
    {
        "loader": "JSONLoader",
        "name": "JSON (.json)",
        "import": "langchain_community.document_loaders.JSONLoader",
        "defaultFor": ["json"],
        "allowdTypes": ["json"],
    },
    {
        "loader": "BSHTMLLoader",
        "name": "BeautifulSoup4 HTML (.html, .htm)",
        "import": "langchain_community.document_loaders.BSHTMLLoader",
        "allowdTypes": ["html", "htm"],
    },
    {
        "loader": "CSVLoader",
        "name": "CSV (.csv)",
        "import": "langchain_community.document_loaders.CSVLoader",
        "defaultFor": ["csv"],
        "allowdTypes": ["csv"],
    },
    {
        "loader": "CoNLLULoader",
        "name": "CoNLL-U (.conllu)",
        "import": "langchain_community.document_loaders.CoNLLULoader",
        "defaultFor": ["conllu"],
        "allowdTypes": ["conllu"],
    },
    {
        "loader": "EverNoteLoader",
        "name": "EverNote (.enex)",
        "import": "langchain_community.document_loaders.EverNoteLoader",
        "defaultFor": ["enex"],
        "allowdTypes": ["enex"],
    },
    {
        "loader": "FacebookChatLoader",
        "name": "Facebook Chat (.json)",
        "import": "langchain_community.document_loaders.FacebookChatLoader",
        "allowdTypes": ["json"],
    },
    {
        "loader": "OutlookMessageLoader",
        "name": "Outlook Message (.msg)",
        "import": "langchain_community.document_loaders.OutlookMessageLoader",
        "defaultFor": ["msg"],
        "allowdTypes": ["msg"],
    },
    {
        "loader": "PyPDFLoader",
        "name": "PyPDF (.pdf)",
        "import": "langchain_community.document_loaders.PyPDFLoader",
        "defaultFor": ["pdf"],
        "allowdTypes": ["pdf"],
    },
    {
        "loader": "STRLoader",
        "name": "Subtitle (.str)",
        "import": "langchain_community.document_loaders.STRLoader",
        "defaultFor": ["str"],
        "allowdTypes": ["str"],
    },
    {
        "loader": "TextLoader",
        "name": "Text (.txt)",
        "import": "langchain_community.document_loaders.TextLoader",
        "defaultFor": ["txt"],
        "allowdTypes": ["txt"],
    },
    {
        "loader": "UnstructuredEmailLoader",
        "name": "Unstructured Email (.eml)",
        "import": "langchain_community.document_loaders.UnstructuredEmailLoader",
        "defaultFor": ["eml"],
        "allowdTypes": ["eml"],
    },
    {
        "loader": "UnstructuredHTMLLoader",
        "name": "Unstructured HTML (.html, .htm)",
        "import": "langchain_community.document_loaders.UnstructuredHTMLLoader",
        "defaultFor": ["html", "htm"],
        "allowdTypes": ["html", "htm"],
    },
    {
        "loader": "UnstructuredMarkdownLoader",
        "name": "Unstructured Markdown (.md)",
        "import": "langchain_community.document_loaders.UnstructuredMarkdownLoader",
        "defaultFor": ["md", "mdx"],
        "allowdTypes": ["md", "mdx"],
    },
    {
        "loader": "UnstructuredPowerPointLoader",
        "name": "Unstructured PowerPoint (.pptx)",
        "import": "langchain_community.document_loaders.UnstructuredPowerPointLoader",
        "defaultFor": ["pptx"],
        "allowdTypes": ["pptx"],
    },
    {
        "loader": "UnstructuredWordLoader",
        "name": "Unstructured Word (.docx)",
        "import": "langchain_community.document_loaders.UnstructuredWordLoader",
        "defaultFor": ["docx"],
        "allowdTypes": ["docx"],
    },
]


MESSAGE_SENDER_AI = "Machine"
MESSAGE_SENDER_USER = "User"
MESSAGE_SENDER_NAME_AI = "AI"
MESSAGE_SENDER_NAME_USER = "User"
