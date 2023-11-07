from typing import Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode
from langflow.template.frontend_node.constants import QA_CHAIN_TYPES
from langflow.template.template.base import Template


class ChainFrontendNode(FrontendNode):
    def add_extra_fields(self) -> None:
        if self.template.type_name == "ConversationalRetrievalChain":
            # add memory
            self.template.add_field(
                TemplateField(
                    field_type="BaseChatMemory",
                    required=True,
                    show=True,
                    name="memory",
                    advanced=False,
                )
            )
            # add return_source_documents
            self.template.add_field(
                TemplateField(
                    field_type="bool",
                    required=False,
                    show=True,
                    name="return_source_documents",
                    advanced=False,
                    value=True,
                    display_name="Return source documents",
                )
            )
            self.template.add_field(
                TemplateField(
                    field_type="str",
                    required=True,
                    is_list=True,
                    show=True,
                    multiline=False,
                    options=QA_CHAIN_TYPES,
                    value=QA_CHAIN_TYPES[0],
                    name="chain_type",
                    advanced=False,
                )
            )

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)

        if "name" == "RetrievalQA" and field.name == "memory":
            field.show = False
            field.required = False

        field.advanced = False
        if "key" in field.name:
            field.password = False
            field.show = False
        if field.name in ["input_key", "output_key"]:
            field.required = True
            field.show = True
            field.advanced = True

        # We should think of a way to deal with this later
        # if field.field_type == "PromptTemplate":
        #     field.field_type = "str"
        #     field.multiline = True
        #     field.show = True
        #     field.advanced = False
        #     field.value = field.value.template

        # Separated for possible future changes
        if field.name == "prompt" and field.value is None:
            field.required = True
            field.show = True
            field.advanced = False
        if field.name == "memory":
            # field.required = False
            field.show = True
            field.advanced = False
        if field.name == "verbose":
            field.required = False
            field.show = False
            field.advanced = True
        if field.name == "llm":
            field.required = True
            field.show = True
            field.advanced = False

        if field.name == "return_source_documents":
            field.required = False
            field.show = True
            field.advanced = True
            field.value = True


class SeriesCharacterChainNode(FrontendNode):
    name: str = "SeriesCharacterChain"
    template: Template = Template(
        type_name="SeriesCharacterChain",
        fields=[
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="character",
            ),
            TemplateField(
                field_type="str",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="series",
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="llm",
                display_name="LLM",
            ),
        ],
    )
    description: str = "SeriesCharacterChain is a chain you can use to have a conversation with a character from a series."  # noqa
    base_classes: list[str] = [
        "LLMChain",
        "BaseCustomChain",
        "Chain",
        "ConversationChain",
        "SeriesCharacterChain",
        "function",
    ]


class TimeTravelGuideChainNode(FrontendNode):
    name: str = "TimeTravelGuideChain"
    template: Template = Template(
        type_name="TimeTravelGuideChain",
        fields=[
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="llm",
                display_name="LLM",
            ),
            TemplateField(
                field_type="BaseChatMemory",
                required=False,
                show=True,
                name="memory",
                advanced=False,
            ),
        ],
    )
    description: str = "Time travel guide chain."
    base_classes: list[str] = [
        "LLMChain",
        "BaseCustomChain",
        "TimeTravelGuideChain",
        "Chain",
        "ConversationChain",
    ]


class MidJourneyPromptChainNode(FrontendNode):
    name: str = "MidJourneyPromptChain"
    template: Template = Template(
        type_name="MidJourneyPromptChain",
        fields=[
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                placeholder="",
                is_list=False,
                show=True,
                advanced=False,
                multiline=False,
                name="llm",
                display_name="LLM",
            ),
            TemplateField(
                field_type="BaseChatMemory",
                required=False,
                show=True,
                name="memory",
                advanced=False,
            ),
        ],
    )
    description: str = "MidJourneyPromptChain is a chain you can use to generate new MidJourney prompts."
    base_classes: list[str] = [
        "LLMChain",
        "BaseCustomChain",
        "Chain",
        "ConversationChain",
        "MidJourneyPromptChain",
    ]


class CombineDocsChainNode(FrontendNode):
    name: str = "CombineDocsChain"
    template: Template = Template(
        type_name="load_qa_chain",
        fields=[
            TemplateField(
                field_type="str",
                required=True,
                is_list=True,
                show=True,
                multiline=False,
                options=QA_CHAIN_TYPES,
                value=QA_CHAIN_TYPES[0],
                name="chain_type",
                advanced=False,
            ),
            TemplateField(
                field_type="BaseLanguageModel",
                required=True,
                show=True,
                name="llm",
                display_name="LLM",
                advanced=False,
            ),
        ],
    )
    description: str = """Load question answering chain."""
    base_classes: list[str] = ["BaseCombineDocumentsChain", "function"]

    def to_dict(self):
        return super().to_dict()

    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        # do nothing and don't return anything
        pass
