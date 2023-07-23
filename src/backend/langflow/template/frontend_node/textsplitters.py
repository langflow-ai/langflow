from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode
from langchain.text_splitter import Language


class TextSplittersFrontendNode(FrontendNode):
    def add_extra_base_classes(self) -> None:
        self.base_classes = ["Document"]
        self.output_types = ["Document"]

    def add_extra_fields(self) -> None:
        self.template.add_field(
            TemplateField(
                field_type="Document",
                required=True,
                show=True,
                name="documents",
                is_list=True,
            )
        )
        name = "separator"
        if self.template.type_name == "CharacterTextSplitter":
            name = "separator"
        elif self.template.type_name == "RecursiveCharacterTextSplitter":
            name = "separators"
            # Add a field for type of separator
            # which will have Text or any value from the
            # Language enum
            options = [x.value for x in Language] + ["Text"]
            options.sort()
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=True,
                    show=True,
                    name="separator_type",
                    advanced=False,
                    is_list=True,
                    options=options,
                    value="Text",
                    display_name="Separator Type",
                )
            )
        self.template.add_field(
            TemplateField(
                field_type="str",
                required=True,
                show=True,
                value="\\n",
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
