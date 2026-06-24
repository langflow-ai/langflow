import contextlib

# A builder backed by a temporarily-unpublished bundle stays None and is skipped.
basic_prompting_graph = None
blog_writer_graph = None
complex_agent_graph = None
document_qa_graph = None
hierarchical_tasks_agent_graph = None
memory_chatbot_graph = None
sequential_tasks_agent_graph = None
vector_store_rag_graph = None

with contextlib.suppress(ImportError):
    from .basic_prompting import basic_prompting_graph
with contextlib.suppress(ImportError):
    from .blog_writer import blog_writer_graph
with contextlib.suppress(ImportError):
    from .complex_agent import complex_agent_graph
with contextlib.suppress(ImportError):
    from .document_qa import document_qa_graph
with contextlib.suppress(ImportError):
    from .hierarchical_tasks_agent import hierarchical_tasks_agent_graph
with contextlib.suppress(ImportError):
    from .memory_chatbot import memory_chatbot_graph
with contextlib.suppress(ImportError):
    from .sequential_tasks_agent import sequential_tasks_agent_graph
with contextlib.suppress(ImportError):
    from .vector_store_rag import vector_store_rag_graph

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
