from langflow import CustomComponent
from langchain.schema import Document
from typing import Any, Dict, List

loaders_info: List[Dict[str, Any]] = [
    {
        "loader": "AirbyteJSONLoader",
        "name": "Airbyte JSON (.jsonl)",
        "import": "langchain.document_loaders.AirbyteJSONLoader",
        "defaultFor": ["jsonl"],
        "allowdTypes": ["jsonl"],
    },
    {
        "loader": "JSONLoader",
        "name": "JSON (.json)",
        "import": "langchain.document_loaders.JSONLoader",
        "defaultFor": ["json"],
        "allowdTypes": ["json"],
    },
    {
        "loader": "BSHTMLLoader",
        "name": "BeautifulSoup4 HTML (.html, .htm)",
        "import": "langchain.document_loaders.BSHTMLLoader",
        "allowdTypes": ["html", "htm"],
    },
    {
        "loader": "CSVLoader",
        "name": "CSV (.csv)",
        "import": "langchain.document_loaders.CSVLoader",
        "defaultFor": ["csv"],
        "allowdTypes": ["csv"],
    },
    {
        "loader": "CoNLLULoader",
        "name": "CoNLL-U (.conllu)",
        "import": "langchain.document_loaders.CoNLLULoader",
        "defaultFor": ["conllu"],
        "allowdTypes": ["conllu"],
    },
    {
        "loader": "EverNoteLoader",
        "name": "EverNote (.enex)",
        "import": "langchain.document_loaders.EverNoteLoader",
        "defaultFor": ["enex"],
        "allowdTypes": ["enex"],
    },
    {
        "loader": "FacebookChatLoader",
        "name": "Facebook Chat (.json)",
        "import": "langchain.document_loaders.FacebookChatLoader",
        "allowdTypes": ["json"],
    },
    {
        "loader": "OutlookMessageLoader",
        "name": "Outlook Message (.msg)",
        "import": "langchain.document_loaders.OutlookMessageLoader",
        "defaultFor": ["msg"],
        "allowdTypes": ["msg"],
    },
    {
        "loader": "PyPDFLoader",
        "name": "PyPDF (.pdf)",
        "import": "langchain.document_loaders.PyPDFLoader",
        "defaultFor": ["pdf"],
        "allowdTypes": ["pdf"],
    },
    {
        "loader": "STRLoader",
        "name": "Subtitle (.str)",
        "import": "langchain.document_loaders.STRLoader",
        "defaultFor": ["str"],
        "allowdTypes": ["str"],
    },
    {
        "loader": "TextLoader",
        "name": "Text (.txt)",
        "import": "langchain.document_loaders.TextLoader",
        "defaultFor": ["txt"],
        "allowdTypes": ["txt"],
    },
    {
        "loader": "UnstructuredEmailLoader",
        "name": "Unstructured Email (.eml)",
        "import": "langchain.document_loaders.UnstructuredEmailLoader",
        "defaultFor": ["eml"],
        "allowdTypes": ["eml"],
    },
    {
        "loader": "UnstructuredHTMLLoader",
        "name": "Unstructured HTML (.html, .htm)",
        "import": "langchain.document_loaders.UnstructuredHTMLLoader",
        "defaultFor": ["html", "htm"],
        "allowdTypes": ["html", "htm"],
    },
    {
        "loader": "UnstructuredMarkdownLoader",
        "name": "Unstructured Markdown (.md)",
        "import": "langchain.document_loaders.UnstructuredMarkdownLoader",
        "defaultFor": ["md"],
        "allowdTypes": ["md"],
    },
    {
        "loader": "UnstructuredPowerPointLoader",
        "name": "Unstructured PowerPoint (.pptx)",
        "import": "langchain.document_loaders.UnstructuredPowerPointLoader",
        "defaultFor": ["pptx"],
        "allowdTypes": ["pptx"],
    },
    {
        "loader": "UnstructuredWordLoader",
        "name": "Unstructured Word (.docx)",
        "import": "langchain.document_loaders.UnstructuredWordLoader",
        "defaultFor": ["docx"],
        "allowdTypes": ["docx"],
    },
]


class FileLoaderComponent(CustomComponent):
    display_name: str = "File Loader"
    description: str = "Generic File Loader"
    beta = True

    def build_config(self):
        loader_options = ["Automatic"] + [
            loader_info["name"] for loader_info in loaders_info
        ]

        file_types = []
        suffixes = []

        for loader_info in loaders_info:
            if "allowedTypes" in loader_info:
                file_types.extend(loader_info["allowedTypes"])
                suffixes.extend([f".{ext}" for ext in loader_info["allowedTypes"]])

        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "field_type": "file",
                "file_types": [
                    "json",
                    "txt",
                    "csv",
                    "jsonl",
                    "html",
                    "htm",
                    "conllu",
                    "enex",
                    "msg",
                    "pdf",
                    "srt",
                    "eml",
                    "md",
                    "pptx",
                    "docx",
                ],
                "suffixes": [
                    ".json",
                    ".txt",
                    ".csv",
                    ".jsonl",
                    ".html",
                    ".htm",
                    ".conllu",
                    ".enex",
                    ".msg",
                    ".pdf",
                    ".srt",
                    ".eml",
                    ".md",
                    ".pptx",
                    ".docx",
                ],
                # "file_types" : file_types,
                # "suffixes": suffixes,
            },
            "loader": {
                "display_name": "Loader",
                "is_list": True,
                "required": True,
                "options": loader_options,
                "value": "Automatic",
            },
            "code": {"show": False},
        }

    def build(self, file_path: str, loader: str) -> Document:
        file_type = file_path.split(".")[-1]

        # Mapeie o nome do loader selecionado para suas informações
        selected_loader_info = None
        for loader_info in loaders_info:
            if loader_info["name"] == loader:
                selected_loader_info = loader_info
                break

        if selected_loader_info is None and loader != "Automatic":
            raise ValueError(f"Loader {loader} not found in the loader info list")

        if loader == "Automatic":
            # Determine o loader automaticamente com base na extensão do arquivo
            default_loader_info = None
            for info in loaders_info:
                if "defaultFor" in info and file_type in info["defaultFor"]:
                    default_loader_info = info
                    break

            if default_loader_info is None:
                raise ValueError(f"No default loader found for file type: {file_type}")

            selected_loader_info = default_loader_info
        if isinstance(selected_loader_info, dict):
            loader_import: str = selected_loader_info["import"]
        else:
            raise ValueError(
                f"Loader info for {loader} is not a dict\nLoader info:\n{selected_loader_info}"
            )
        module_name, class_name = loader_import.rsplit(".", 1)

        try:
            # Importe o loader dinamicamente
            loader_module = __import__(module_name, fromlist=[class_name])
            loader_instance = getattr(loader_module, class_name)
        except ImportError as e:
            raise ValueError(
                f"Loader {loader} could not be imported\nLoader info:\n{selected_loader_info}"
            ) from e

        result = loader_instance(file_path=file_path)
        return result.load()
