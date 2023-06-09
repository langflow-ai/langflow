from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode


class TextSplittersFrontendNode(FrontendNode):
    def add_extra_fields(self) -> None:
        self.template.add_field(
            TemplateField(
                field_type="BaseLoader",
                required=True,
                show=True,
                name="documents",
            )
        )
        name = "separator"
        if self.template.type_name == "CharacterTextSplitter":
            name = "separator"
        elif self.template.type_name == "RecursiveCharacterTextSplitter":
            name = "separators"
        self.template.add_field(
            TemplateField(
                field_type="str",
                required=True,
                show=True,
                value=".",
                name=name,
                display_name="Separator",
            )
        )
        self.template.add_field(
            TemplateField(
                field_type="int",
                required=True,
                show=True,
                value=1000,
                name="chunk_size",
                display_name="Chunk Size",
            )
        )
        self.template.add_field(
            TemplateField(
                field_type="int",
                required=True,
                show=True,
                value=200,
                name="chunk_overlap",
                display_name="Chunk Overlap",
            )
        )
