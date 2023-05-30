from typing import Dict, List, Optional, Type

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode

class DocumentLoaderFrontNode(FrontendNode):

    @staticmethod
    def build_template(suffixes: list, fileTypes: list, name: str = "file_path"
        ) -> Dict:
            """Build a template field for a document loader."""   
            return TemplateField(
                field_type="file",
                required=True,
                show=True,
                name=name,
                value="",
                suffixes=suffixes,
                fileTypes=fileTypes,
                )

    def get_file_path_template(self):
        return {
            "AirbyteJSONLoader": self.build_template(
                suffixes=[".json"], fileTypes=["json"]
            ),
            "CoNLLULoader": self.build_template(
                suffixes=[".csv"], fileTypes=["csv"]
            ),
            "CSVLoader": self.build_template(
                suffixes=[".csv"], fileTypes=["csv"]
            ),
            "UnstructuredEmailLoader": self.build_template(
                suffixes=[".eml"], fileTypes=["eml"]
            ),
            "EverNoteLoader": self.build_template(
                suffixes=[".xml"], fileTypes=["xml"]
            ),
            "FacebookChatLoader": self.build_template(
                suffixes=[".json"], fileTypes=["json"]
            ),
            "GutenbergLoader": self.build_template(
                suffixes=[".txt"], fileTypes=["txt"]
            ),
            "BSHTMLLoader": self.build_template(
                suffixes=[".html"], fileTypes=["html"]
            ),
            "UnstructuredHTMLLoader": self.build_template(
                suffixes=[".html"], fileTypes=["html"]
            ),
            "UnstructuredImageLoader": self.build_template(
                suffixes=[".jpg", ".jpeg", ".png", ".gif", ".bmp"],
                fileTypes=["jpg", "jpeg", "png", "gif", "bmp"],
            ),
            "UnstructuredMarkdownLoader": self.build_template(
                suffixes=[".md"], fileTypes=["md"]
            ),
            "PyPDFLoader": self.build_template(
                suffixes=[".pdf"], fileTypes=["pdf"]
            ),
            "UnstructuredPowerPointLoader": self.build_template(
                suffixes=[".pptx", ".ppt"], fileTypes=["pptx", "ppt"]
            ),
            "SRTLoader": self.build_template(
                suffixes=[".srt"], fileTypes=["srt"]
            ),
            "TelegramChatLoader": self.build_template(
                suffixes=[".json"], fileTypes=["json"]
            ),
            "TextLoader": self.build_template(
                suffixes=[".txt"], fileTypes=["txt"]
            ),
            "UnstructuredWordDocumentLoader": self.build_template(
                suffixes=[".docx", ".doc"], fileTypes=["docx", "doc"]
            ),
        }
    
    def add_extra_fields(self) -> None:  
        file_path_templates = self.get_file_path_template()

        if self.template.type_name in file_path_templates:  
            self.template.add_field(file_path_templates[self.template.type_name])
        elif self.template.type_name in {
            "WebBaseLoader",
            "AZLyricsLoader",
            "CollegeConfidentialLoader",
            "HNLoader",
            "IFixitLoader",
            "IMSDbLoader",
        }:
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=True,
                    show=True,
                    name="web_path",
                    value="",
                    display_name="Web Page",
                )
            )
        elif self.template.type_name in {"GitbookLoader"}:
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=True,
                    show=True,
                    name="web_page",
                    value="",
                    display_name="Web Page",
                )
            )
        elif self.template.type_name in {"ReadTheDocsLoader"}:
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=True,
                    show=True,
                    name="path",
                    value="",
                    display_name="Web Page",
                )
            )