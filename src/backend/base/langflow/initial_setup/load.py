from pathlib import Path
from .starter_projects import (
    basic_prompting_graph,
    blog_writer_graph,
    document_qa_graph,
    memory_chatbot_graph,
    vector_store_rag_graph,
)


def get_starter_projects_graphs():
    return [
        basic_prompting_graph(),
        blog_writer_graph(),
        document_qa_graph(),
        memory_chatbot_graph(),
        vector_store_rag_graph(),
    ]


def get_starter_projects_dump():
    return [g.dump() for g in get_starter_projects_graphs()]


def get_starter_projects_file_names():
    """Get a list of file names from the starter projects directory.
    
    This function reads file names directly from the filesystem without
    importing any modules to avoid dependency issues.
    """
    try:
        current_dir = Path(__file__).parent
        starter_projects_dir = current_dir / "starter_projects"
        
        file_names = []
        
        if starter_projects_dir.exists() and starter_projects_dir.is_dir():
            for file_path in starter_projects_dir.iterdir():
                if file_path.is_file() and file_path.name != "__init__.py":
                    file_names.append(file_path.name)
        
        return sorted(file_names)
    except Exception as e:
        # Return empty list if there's any error accessing the directory
        return []
