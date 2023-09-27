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
        file_types=fileTypes,
    )


class DocumentLoaderFrontNode(FrontendNode):
    def add_extra_base_classes(self) -> None:
        self.base_classes = ["Document"]
        self.output_types = ["Document"]

    file_path_templates = {
        "AirbyteJSONLoader": build_file_field(suffixes=[".json"], fileTypes=["json"]),
        "CoNLLULoader": build_file_field(suffixes=[".csv"], fileTypes=["csv"]),
        "CSVLoader": build_file_field(suffixes=[".csv"], fileTypes=["csv"]),
        "UnstructuredEmailLoader": build_file_field(
            suffixes=[".eml"], fileTypes=["eml"]
        ),
        "EverNoteLoader": build_file_field(suffixes=[".xml"], fileTypes=["xml"]),
        "FacebookChatLoader": build_file_field(suffixes=[".json"], fileTypes=["json"]),
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
        elif self.template.type_name in {"SlackDirectoryLoader"}:
            self.template.add_field(
                TemplateField(
                    field_type="file",
                    required=True,
                    show=True,
                    name="zip_path",
                    value="",
                    display_name="Path to zip file",
                    suffixes=[".zip"],
                    file_types=["zip"],
                )
            )
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=False,
                    show=True,
                    name="workspace_url",
                    value="",
                    display_name="Workspace URL",
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
            "GutenbergLoader",
        }:
            name = "web_path"
        elif self.template.type_name in {"GutenbergLoader"}:
            name = "file_path"
        elif self.template.type_name in {"GitbookLoader"}:
            name = "web_page"
        elif self.template.type_name in {
            "DirectoryLoader",
            "ReadTheDocsLoader",
            "NotionDirectoryLoader",
            "PyPDFDirectoryLoader",
        }:
            name = "path"
            display_name = "Local directory"
        if name:
            if self.template.type_name in {"DirectoryLoader"}:
                for field in build_directory_loader_fields():
                    self.template.add_field(field)
            else:
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
            # add a metadata field of type dict
        self.template.add_field(
            TemplateField(
                field_type="dict",
                required=False,
                show=True,
                name="metadata",
                value={},
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


def build_directory_loader_fields():
    # if loader_kwargs is None:
    #         loader_kwargs = {}
    # self.path = path
    # self.glob = glob
    # self.load_hidden = load_hidden
    # self.loader_cls = loader_cls
    # self.loader_kwargs = loader_kwargs
    # self.silent_errors = silent_errors
    # self.recursive = recursive
    # self.show_progress = show_progress
    # self.use_multithreading = use_multithreading
    # self.max_concurrency = max_concurrency
    # Based on the above fields, we can build the following fields:
    # path, glob, load_hidden, silent_errors, recursive, show_progress, use_multithreading, max_concurrency
    # path
    path = TemplateField(
        field_type="str",
        required=True,
        show=True,
        name="path",
        value="",
        display_name="Local directory",
        advanced=False,
    )
    # glob
    glob = TemplateField(
        field_type="str",
        required=True,
        show=True,
        name="glob",
        value="**/*.txt",
        display_name="glob",
        advanced=False,
    )
    # load_hidden
    load_hidden = TemplateField(
        field_type="bool",
        required=False,
        show=True,
        name="load_hidden",
        value="False",
        display_name="Load hidden files",
        advanced=True,
    )
    # silent_errors
    silent_errors = TemplateField(
        field_type="bool",
        required=False,
        show=True,
        name="silent_errors",
        value="False",
        display_name="Silent errors",
        advanced=True,
    )
    # recursive
    recursive = TemplateField(
        field_type="bool",
        required=False,
        show=True,
        name="recursive",
        value="True",
        display_name="Recursive",
        advanced=True,
    )

    # use_multithreading
    use_multithreading = TemplateField(
        field_type="bool",
        required=False,
        show=True,
        name="use_multithreading",
        value="True",
        display_name="Use multithreading",
        advanced=True,
    )
    # max_concurrency
    max_concurrency = TemplateField(
        field_type="int",
        required=False,
        show=True,
        name="max_concurrency",
        value=10,
        display_name="Max concurrency",
        advanced=True,
    )

    return (
        path,
        glob,
        load_hidden,
        silent_errors,
        recursive,
        use_multithreading,
        max_concurrency,
    )
