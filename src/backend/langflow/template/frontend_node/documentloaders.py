from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class DocumentLoaderFrontNode(FrontendNode):
    @staticmethod
    def build_template(
        suffixes: list, fileTypes: list, name: str = "file_path"
    ) -> TemplateField:
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

    file_path_templates = {
        "AirbyteJSONLoader": build_template(suffixes=[".json"], fileTypes=["json"]),
        "CoNLLULoader": build_template(suffixes=[".csv"], fileTypes=["csv"]),
        "CSVLoader": build_template(suffixes=[".csv"], fileTypes=["csv"]),
        "UnstructuredEmailLoader": build_template(suffixes=[".eml"], fileTypes=["eml"]),
        "EverNoteLoader": build_template(suffixes=[".xml"], fileTypes=["xml"]),
        "FacebookChatLoader": build_template(suffixes=[".json"], fileTypes=["json"]),
        "GutenbergLoader": build_template(suffixes=[".txt"], fileTypes=["txt"]),
        "BSHTMLLoader": build_template(suffixes=[".html"], fileTypes=["html"]),
        "UnstructuredHTMLLoader": build_template(
            suffixes=[".html"], fileTypes=["html"]
        ),
        "UnstructuredImageLoader": build_template(
            suffixes=[".jpg", ".jpeg", ".png", ".gif", ".bmp"],
            fileTypes=["jpg", "jpeg", "png", "gif", "bmp"],
        ),
        "UnstructuredMarkdownLoader": build_template(
            suffixes=[".md"], fileTypes=["md"]
        ),
        "PyPDFLoader": build_template(suffixes=[".pdf"], fileTypes=["pdf"]),
        "UnstructuredPowerPointLoader": build_template(
            suffixes=[".pptx", ".ppt"], fileTypes=["pptx", "ppt"]
        ),
        "SRTLoader": build_template(suffixes=[".srt"], fileTypes=["srt"]),
        "TelegramChatLoader": build_template(suffixes=[".json"], fileTypes=["json"]),
        "TextLoader": build_template(suffixes=[".txt"], fileTypes=["txt"]),
        "UnstructuredWordDocumentLoader": build_template(
            suffixes=[".docx", ".doc"], fileTypes=["docx", "doc"]
        ),
    }

    def add_extra_fields(self) -> None:
        name = None
        if self.template.type_name in self.file_path_templates:
            self.template.add_field(self.file_path_templates[self.template.type_name])
        elif self.template.type_name in {
            "WebBaseLoader",
            "AZLyricsLoader",
            "CollegeConfidentialLoader",
            "HNLoader",
            "IFixitLoader",
            "IMSDbLoader",
        }:
            name = "web_path"
        elif self.template.type_name in {"GitbookLoader"}:
            name = "web_page"
        elif self.template.type_name in {"ReadTheDocsLoader"}:
            name = "path"
        if name:
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=True,
                    show=True,
                    name=name,
                    value="",
                    display_name="Web Page",
                )
            )
