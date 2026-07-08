from importlib import import_module

from .basic_prompting import basic_prompting_graph
from .blog_writer import blog_writer_graph
from .document_qa import document_qa_graph
from .memory_chatbot import memory_chatbot_graph
from .vector_store_rag import vector_store_rag_graph

_LAZY_STARTER_PROJECTS = {
    "complex_agent_graph": ".complex_agent",
    "hierarchical_tasks_agent_graph": ".hierarchical_tasks_agent",
    "sequential_tasks_agent_graph": ".sequential_tasks_agent",
}

__all__ = [
    "basic_prompting_graph",
    "blog_writer_graph",
    "complex_agent_graph",
    "document_qa_graph",
    "hierarchical_tasks_agent_graph",
    "memory_chatbot_graph",
    "sequential_tasks_agent_graph",
    "vector_store_rag_graph",
]


def __getattr__(name: str):
    if name in _LAZY_STARTER_PROJECTS:
        module = import_module(_LAZY_STARTER_PROJECTS[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
