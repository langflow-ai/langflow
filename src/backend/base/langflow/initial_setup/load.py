from collections.abc import Callable
from typing import Any

from langflow.utils.i18n_keys import safe_flow_key

from .starter_projects import (
    basic_prompting_graph,
    blog_writer_graph,
    document_qa_graph,
    memory_chatbot_graph,
    vector_store_rag_graph,
)

# Each starter project is declared alongside its canonical name and description so
# that reordering cannot associate a graph with the wrong metadata. The names and
# descriptions are kept in sync with ``initial_setup/starter_projects/*.json``.
STARTER_PROJECTS: list[tuple[Callable[[], Any], str, str]] = [
    (
        basic_prompting_graph,
        "Basic Prompting",
        "Perform basic prompting with an OpenAI model.",
    ),
    (
        blog_writer_graph,
        "Blog Writer",
        (
            "Write blog posts from web references using an Agent. URL fetches references, you provide the "
            "topic via Chat Input, and the Agent writes a grounded post. Core components only."
        ),
    ),
    (
        document_qa_graph,
        "Document Q&A",
        (
            "Ask questions about your own document using a built-in Knowledge Base (RAG). File ingests into "
            "the KB; an Agent answers from retrieved context. No external vector database required."
        ),
    ),
    (
        memory_chatbot_graph,
        "Memory Chatbot",
        (
            "Create a chatbot that saves and references previous messages, enabling the model to maintain "
            "context throughout the conversation."
        ),
    ),
    (
        vector_store_rag_graph,
        "Vector Store RAG",
        "Load your data for chat context with Retrieval Augmented Generation.",
    ),
]


def get_starter_projects_graphs():
    return [build_graph() for build_graph, _name, _description in STARTER_PROJECTS]


def get_starter_projects_dump():
    return [
        {
            **build_graph().dump(name=name, description=description),
            "name_key": safe_flow_key(name),
        }
        for build_graph, name, description in STARTER_PROJECTS
    ]
