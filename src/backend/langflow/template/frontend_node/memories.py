from typing import Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode
from langflow.template.template.base import Template
from langchain.memory.chat_message_histories.postgres import DEFAULT_CONNECTION_STRING


class MemoryFrontendNode(FrontendNode):
    #! Needs testing
    def add_extra_fields(self) -> None:
        # chat history should have another way to add common field?
        # prevent adding incorect field in ChatMessageHistory
        base_message_classes = ["BaseEntityStore", "BaseChatMessageHistory"]
        if any(base_class in self.base_classes for base_class in base_message_classes):
            return

        # add return_messages field
        self.template.add_field(
            TemplateField(
                field_type="bool",
                required=False,
                show=True,
                name="return_messages",
                advanced=False,
                value=False,
            )
        )
        # add input_key and output_key str fields
        self.template.add_field(
            TemplateField(
                field_type="str",
                required=False,
                show=True,
                name="input_key",
                advanced=True,
                value="",
            )
        )
        if self.template.type_name not in {"VectorStoreRetrieverMemory"}:
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=False,
                    show=True,
                    name="output_key",
                    advanced=True,
                    value="",
                )
            )

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)

        if not isinstance(field.value, str):
            field.value = None
        if field.name == "k":
            field.required = True
            field.show = True
            field.field_type = "int"
            field.value = 10
            field.display_name = "Memory Size"
        field.password = False
        if field.name == "return_messages":
            field.required = False
            field.show = True
            field.advanced = False
        if field.name in ["input_key", "output_key"]:
            field.required = False
            field.show = True
            field.advanced = False
            field.value = ""
        if field.name == "memory_key":
            field.value = "chat_history"
        if field.name == "chat_memory":
            field.show = True
            field.advanced = False
            field.required = False
        if field.name == "url":
            field.show = True
        if field.name == "entity_store":
            field.show = True
        if name == "SQLiteEntityStore":
            field.show = True


class PostgresChatMessageHistoryFrontendNode(MemoryFrontendNode):
    name: str = "PostgresChatMessageHistory"
    template: Template = Template(
        type_name="PostgresChatMessageHistory",
        fields=[
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=False,
                name="session_id",
            ),
            TemplateField(
                field_type="str",
                required=True,
                show=True,
                name="connection_string",
                value=DEFAULT_CONNECTION_STRING,
            ),
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                multiline=False,
                value="message_store",
                name="table_name",
            ),
        ],
    )
    description: str = "Memory store with Postgres"
    base_classes: list[str] = ["PostgresChatMessageHistory", "BaseChatMessageHistory"]
