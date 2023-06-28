from typing import Optional
from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


def build_file_field(
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


class DocumentLoaderFrontNode(FrontendNode):
    file_path_templates = {
        "AirbyteJSONLoader": build_file_field(suffixes=[".json"], fileTypes=["json"]),
        "CoNLLULoader": build_file_field(suffixes=[".csv"], fileTypes=["csv"]),
        "CSVLoader": build_file_field(suffixes=[".csv"], fileTypes=["csv"]),
        "UnstructuredEmailLoader": build_file_field(
            suffixes=[".eml"], fileTypes=["eml"]
        ),
        "SlackDirectoryLoader": build_file_field(suffixes=[".zip"], fileTypes=["zip"]),
        "EverNoteLoader": build_file_field(suffixes=[".xml"], fileTypes=["xml"]),
        "FacebookChatLoader": build_file_field(suffixes=[".json"], fileTypes=["json"]),
        "GutenbergLoader": build_file_field(suffixes=[".txt"], fileTypes=["txt"]),
        "BSHTMLLoader": build_file_field(suffixes=[".html"], fileTypes=["html"]),
        "UnstructuredHTMLLoader": build_file_field(
            suffixes=[".html"], fileTypes=["html"]
        ),
        "UnstructuredImageLoader": build_file_field(
            suffixes=[".jpg", ".jpeg", ".png", ".gif", ".bmp"],
            fileTypes=["jpg", "jpeg", "png", "gif", "bmp"],
        ),
        "UnstructuredMarkdownLoader": build_file_field(
            suffixes=[".md"], fileTypes=["md"]
        ),
        "PyPDFLoader": build_file_field(suffixes=[".pdf"], fileTypes=["pdf"]),
        "UnstructuredPowerPointLoader": build_file_field(
            suffixes=[".pptx", ".ppt"], fileTypes=["pptx", "ppt"]
        ),
        "SRTLoader": build_file_field(suffixes=[".srt"], fileTypes=["srt"]),
        "TelegramChatLoader": build_file_field(suffixes=[".json"], fileTypes=["json"]),
        "TextLoader": build_file_field(suffixes=[".txt"], fileTypes=["txt"]),
        "UnstructuredWordDocumentLoader": build_file_field(
            suffixes=[".docx", ".doc"], fileTypes=["docx", "doc"]
        ),
    }

    def add_extra_fields(self) -> None:
        name = None
        display_name = "Web Page"
        if self.template.type_name in {"GitLoader"}:
            # Add fields repo_path, clone_url, branch and file_filter
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=True,
                    show=True,
                    name="repo_path",
                    value="",
                    display_name="Path to repository",
                    advanced=False,
                )
            )
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=False,
                    show=True,
                    name="clone_url",
                    value="",
                    display_name="Clone URL",
                    advanced=False,
                )
            )
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=True,
                    show=True,
                    name="branch",
                    value="",
                    display_name="Branch",
                    advanced=False,
                )
            )
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=False,
                    show=True,
                    name="file_filter",
                    value="",
                    display_name="File extensions (comma-separated)",
                    advanced=False,
                )
            )

        elif self.template.type_name in self.file_path_templates:
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
        elif self.template.type_name in {
            "DirectoryLoader",
            "ReadTheDocsLoader",
            "NotionDirectoryLoader",
        }:
            name = "path"
            display_name = "Local directory"
        if name:
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=True,
                    show=True,
                    name=name,
                    value="",
                    display_name=display_name,
                )
            )
            if self.template.type_name in {"DirectoryLoader"}:
                self.template.add_field(
                    TemplateField(
                        field_type="str",
                        required=True,
                        show=True,
                        name="glob",
                        value="**/*.txt",
                        display_name="glob",
                    )
                )
            # add a metadata field of type dict
        self.template.add_field(
            TemplateField(
                field_type="code",
                required=True,
                show=True,
                name="metadata",
                value="{}",
                display_name="Metadata",
                multiline=False,
            )
        )

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)
        if field.name == "metadata":
            field.show = True
            field.advanced = False
        field.show = True
