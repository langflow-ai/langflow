from .starter_projects import (
    blog_writer_graph,
    document_qa_graph,
    memory_chatbot_graph,
    sequential_tasks_agent_graph,
    vector_store_rag_graph,
)


def get_all_graphs():
    return [
        blog_writer_graph(),
        document_qa_graph(),
        memory_chatbot_graph(),
        vector_store_rag_graph(),
        sequential_tasks_agent_graph(),
    ]


def get_all_graphs_dump():
    return [g.dump() for g in get_all_graphs()]
