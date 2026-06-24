from .starter_projects import (
    basic_prompting_graph,
    blog_writer_graph,
    document_qa_graph,
    memory_chatbot_graph,
    vector_store_rag_graph,
)


def get_starter_projects_graphs():
    builders = [
        basic_prompting_graph,
        blog_writer_graph,
        document_qa_graph,
        memory_chatbot_graph,
        vector_store_rag_graph,
    ]
    return [builder() for builder in builders if builder is not None]


def get_starter_projects_dump():
    return [g.dump() for g in get_starter_projects_graphs()]
