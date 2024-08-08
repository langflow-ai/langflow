from .starter_projects import blog_writer_graph, document_qa_graph, memory_chatbot_graph, vector_store_rag_graph


def get_all_graphs():
    return [
        blog_writer_graph(),
        document_qa_graph(),
        memory_chatbot_graph(),
        vector_store_rag_graph(),
    ]


def get_all_graphs_dump():
    return [
        blog_writer_graph().dump(),
        document_qa_graph().dump(),
        memory_chatbot_graph().dump(),
        vector_store_rag_graph().dump(),
    ]
