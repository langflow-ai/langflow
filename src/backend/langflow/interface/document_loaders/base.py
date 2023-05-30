from typing import Dict, List, Optional

from langflow.interface.base import LangChainTypeCreator
from langflow.interface.custom_lists import documentloaders_type_to_cls_dict
from langflow.settings import settings
from langflow.utils.logger import logger
from langflow.utils.util import build_template_from_class


def build_file_path_template(
    suffixes: list, fileTypes: list, name: str = "file_path"
) -> Dict:
    """Build a file path template for a document loader."""
    return {
        "type": "file",
        "required": True,
        "show": True,
        "name": name,
        "value": "",
        "suffixes": suffixes,
        "fileTypes": fileTypes,
    }


class DocumentLoaderCreator(LangChainTypeCreator):
    type_name: str = "documentloaders"

    @property
    def type_to_loader_dict(self) -> Dict:
        return documentloaders_type_to_cls_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        """Get the signature of a document loader."""
        try:
            signature = build_template_from_class(
                name, documentloaders_type_to_cls_dict
            )

            file_path_templates = {
                "AirbyteJSONLoader": build_file_path_template(
                    suffixes=[".json"], fileTypes=["json"]
                ),
                "CoNLLULoader": build_file_path_template(
                    suffixes=[".csv"], fileTypes=["csv"]
                ),
                "CSVLoader": build_file_path_template(
                    suffixes=[".csv"], fileTypes=["csv"]
                ),
                "UnstructuredEmailLoader": build_file_path_template(
                    suffixes=[".eml"], fileTypes=["eml"]
                ),
                "EverNoteLoader": build_file_path_template(
                    suffixes=[".xml"], fileTypes=["xml"]
                ),
                "FacebookChatLoader": build_file_path_template(
                    suffixes=[".json"], fileTypes=["json"]
                ),
                "GutenbergLoader": build_file_path_template(
                    suffixes=[".txt"], fileTypes=["txt"]
                ),
                "BSHTMLLoader": build_file_path_template(
                    suffixes=[".html"], fileTypes=["html"]
                ),
                "UnstructuredHTMLLoader": build_file_path_template(
                    suffixes=[".html"], fileTypes=["html"]
                ),
                "UnstructuredImageLoader": build_file_path_template(
                    suffixes=[".jpg", ".jpeg", ".png", ".gif", ".bmp"],
                    fileTypes=["jpg", "jpeg", "png", "gif", "bmp"],
                ),
                "UnstructuredMarkdownLoader": build_file_path_template(
                    suffixes=[".md"], fileTypes=["md"]
                ),
                "PyPDFLoader": build_file_path_template(
                    suffixes=[".pdf"], fileTypes=["pdf"]
                ),
                "UnstructuredPowerPointLoader": build_file_path_template(
                    suffixes=[".pptx", ".ppt"], fileTypes=["pptx", "ppt"]
                ),
                "SRTLoader": build_file_path_template(
                    suffixes=[".srt"], fileTypes=["srt"]
                ),
                "TelegramChatLoader": build_file_path_template(
                    suffixes=[".json"], fileTypes=["json"]
                ),
                "TextLoader": build_file_path_template(
                    suffixes=[".txt"], fileTypes=["txt"]
                ),
                "UnstructuredWordDocumentLoader": build_file_path_template(
                    suffixes=[".docx", ".doc"], fileTypes=["docx", "doc"]
                ),
                "SlackDirectoryLoader": build_file_path_template(
                    suffixes=[".zip"], fileTypes=["zip"]
                ),
            }

            if name in file_path_templates:
                signature["template"]["file_path"] = file_path_templates[name]
            elif name in {
                "WebBaseLoader",
                "AZLyricsLoader",
                "CollegeConfidentialLoader",
                "HNLoader",
                "IFixitLoader",
                "IMSDbLoader",
            }:
                signature["template"]["web_path"] = {
                    "type": "str",
                    "required": True,
                    "show": True,
                    "name": "web_path",
                    "value": "",
                    "display_name": "Web Page",
                }
            elif name in {"GitbookLoader"}:
                signature["template"]["web_page"] = {
                    "type": "str",
                    "required": True,
                    "show": True,
                    "name": "web_page",
                    "value": "",
                    "display_name": "Web Page",
                }
            elif name in {"ReadTheDocsLoader", "NotionDirectoryLoader"}:
                signature["template"]["path"] = {
                    "type": "str",
                    "required": True,
                    "show": True,
                    "name": "path",
                    "value": "",
                    "display_name": "Web Page",
                }

            return signature
        except ValueError as exc:
            raise ValueError(f"Documment Loader {name} not found") from exc
        except AttributeError as exc:
            logger.error(f"Documment Loader {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return [
            documentloader.__name__
            for documentloader in self.type_to_loader_dict.values()
            if documentloader.__name__ in settings.documentloaders or settings.dev
        ]


documentloader_creator = DocumentLoaderCreator()
