from typing import Optional

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode
from langflow.template.template.base import Template


class ChainFrontendNode(FrontendNode):
    @staticmethod
    def format_field(field: TemplateField, name: Optional[str] = None) -> None:
        FrontendNode.format_field(field, name)

        field.advanced = False
        if "key" in field.name:
            field.password = False
            field.show = False
        if field.name in ["input_key", "output_key"]:
            field.required = True
            field.show = True
            field.advanced = True

        # Separated for possible future changes
        if field.name == "prompt" and field.value is None:
            field.required = True
            field.show = True
            field.advanced = False
        if field.name == "memory":
            field.required = False
            field.show = True
            field.advanced = False
        if field.name == "verbose":
            field.required = False
            field.show = True
            field.advanced = True
        if field.name == "llm":
            field.required = True
            field.show = True
            field.advanced = False


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
    description: str = "Time travel guide chain to be used in the flow."
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
