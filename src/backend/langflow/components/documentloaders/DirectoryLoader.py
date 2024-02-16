from typing import Any, Dict, List

from langchain.docstore.document import Document
from langchain.document_loaders.directory import DirectoryLoader
from langflow import CustomComponent


class DirectoryLoaderComponent(CustomComponent):
    display_name = "DirectoryLoader"
    description = "Load from a directory."

    def build_config(self) -> Dict[str, Any]:
        return {
            "glob": {"display_name": "Glob Pattern", "value": "**/*.txt"},
            "load_hidden": {"display_name": "Load Hidden Files", "value": False, "advanced": True},
            "max_concurrency": {"display_name": "Max Concurrency", "value": 10, "advanced": True},
            "metadata": {"display_name": "Metadata", "value": {}},
            "path": {"display_name": "Local Directory"},
            "recursive": {"display_name": "Recursive", "value": True, "advanced": True},
            "silent_errors": {"display_name": "Silent Errors", "value": False, "advanced": True},
            "use_multithreading": {"display_name": "Use Multithreading", "value": True, "advanced": True},
        }

    def build(
        self,
        glob: str,
        path: str,
        max_concurrency: int = 2,
        load_hidden: bool = False,
        recursive: bool = True,
        silent_errors: bool = False,
        use_multithreading: bool = True,
    ) -> List[Document]:
        return DirectoryLoader(
            glob=glob,
            path=path,
            load_hidden=load_hidden,
            max_concurrency=max_concurrency,
            recursive=recursive,
            silent_errors=silent_errors,
            use_multithreading=use_multithreading,
        ).load()
