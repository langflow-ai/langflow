from .starter_projects import (
    basic_prompting_graph,
    blog_writer_graph,
    document_qa_graph,
    memory_chatbot_graph,
    vector_store_rag_graph,
)

# Name and description for each starter project, kept in sync with the
# corresponding files in ``initial_setup/starter_projects/*.json``.
STARTER_PROJECT_METADATA: list[tuple[str, str]] = [
    ("Basic Prompting", "Perform basic prompting with an OpenAI model."),
    (
        "Blog Writer",
        (
            "Write blog posts from web references using an Agent. URL fetches references, you provide the "
            "topic via Chat Input, and the Agent writes a grounded post. Core components only."
        ),
    ),
    (
        "Document Q&A",
        (
            "Ask questions about your own document using a built-in Knowledge Base (RAG). File ingests into "
            "the KB; an Agent answers from retrieved context. No external vector database required."
        ),
    ),
    (
        "Memory Chatbot",
        (
            "Create a chatbot that saves and references previous messages, enabling the model to maintain "
            "context throughout the conversation."
        ),
    ),
    ("Vector Store RAG", "Load your data for chat context with Retrieval Augmented Generation."),
]


def get_starter_projects_graphs():
    return [
        basic_prompting_graph(),
        blog_writer_graph(),
        document_qa_graph(),
        memory_chatbot_graph(),
        vector_store_rag_graph(),
    ]


def get_starter_projects_dump():
    graphs = get_starter_projects_graphs()
    return [
        graph.dump(name=name, description=description)
        for graph, (name, description) in zip(graphs, STARTER_PROJECT_METADATA, strict=True)
    ]
