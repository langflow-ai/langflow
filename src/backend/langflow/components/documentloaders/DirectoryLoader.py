from langflow import CustomComponent
from langchain.docstore.document import Document
from typing import Optional, Dict, Any


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
        load_hidden: Optional[bool] = False,
        max_concurrency: Optional[int] = 10,
        metadata: Optional[dict] = {},
        recursive: Optional[bool] = True,
        silent_errors: Optional[bool] = False,
        use_multithreading: Optional[bool] = True,
    ) -> Document:
        return Document(
            glob=glob,
            path=path,
            load_hidden=load_hidden,
            max_concurrency=max_concurrency,
            metadata=metadata,
            recursive=recursive,
            silent_errors=silent_errors,
            use_multithreading=use_multithreading,
        )
