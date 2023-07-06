from langflow.interface.agents.base import agent_creator
from langflow.interface.chains.base import chain_creator
from langflow.interface.document_loaders.base import documentloader_creator
from langflow.interface.embeddings.base import embedding_creator
from langflow.interface.llms.base import llm_creator
from langflow.interface.memories.base import memory_creator
from langflow.interface.prompts.base import prompt_creator
from langflow.interface.text_splitters.base import textsplitter_creator
from langflow.interface.toolkits.base import toolkits_creator
from langflow.interface.tools.base import tool_creator
from langflow.interface.utilities.base import utility_creator
from langflow.interface.vector_store.base import vectorstore_creator
from langflow.interface.wrappers.base import wrapper_creator
from langflow.interface.output_parsers.base import output_parser_creator
from langflow.interface.tools.custom import CustomComponent

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.tools import CustomComponentNode
from langflow.interface.retrievers.base import retriever_creator

from langflow.utils.util import get_base_classes

from fastapi import HTTPException
import traceback

# Used to get the base_classes list
from langchain.chains import ConversationChain  # noqa: F401
from langchain.llms.base import BaseLLM  # noqa: F401
from langchain.tools import Tool  # noqa: F401


def get_type_list():
    """Get a list of all langchain types"""
    all_types = build_langchain_types_dict()

    # all_types.pop("tools")

    for key, value in all_types.items():
        all_types[key] = [item["template"]["_type"] for item in value.values()]

    return all_types


def build_langchain_types_dict():  # sourcery skip: dict-assign-update-to-union
    """Build a dictionary of all langchain types"""

    all_types = {}

    creators = [
        chain_creator,
        agent_creator,
        prompt_creator,
        llm_creator,
        memory_creator,
        tool_creator,
        toolkits_creator,
        wrapper_creator,
        embedding_creator,
        vectorstore_creator,
        documentloader_creator,
        textsplitter_creator,
        utility_creator,
        output_parser_creator,
        retriever_creator,
    ]

    all_types = {}
    for creator in creators:
        created_types = creator.to_dict()
        if created_types[creator.type_name].values():
            all_types.update(created_types)
    return all_types


# TODO: Move to correct place
def add_new_custom_field(template, field_name: str, field_type: str):
    new_field = TemplateField(
        name=field_name, field_type=field_type, show=True, required=True, advanced=False
    )
    template.get("template")[field_name] = new_field.to_dict()
    template.get("custom_fields")[field_name] = None

    return template


# TODO: Move to correct place
def add_code_field(template, raw_code):
    # Field with the Python code to allow update
    code_field = {
        "code": {
            "dynamic": True,
            "required": True,
            "placeholder": "",
            "show": True,
            "multiline": True,
            "value": raw_code,
            "password": False,
            "name": "code",
            "advanced": False,
            "type": "code",
            "list": False,
        }
    }
    template.get("template")["code"] = code_field.get("code")

    return template


def build_langchain_template_custom_component(extractor: CustomComponent):
    # Build base "CustomComponent" template
    template = CustomComponentNode().to_dict().get(type(extractor).__name__)

    function_args, return_type = extractor.args_and_return_type
    raw_code = extractor.code

    # Add extra fields
    for extra_field in function_args:
        def_field = extra_field[0]
        def_type = extra_field[1]

        if def_field != "self":
            # TODO: Validate type - if is possible to render into frontend
            if not def_type:
                def_type = "str"

            template = add_new_custom_field(template, def_field, def_type)

    template = add_code_field(template, raw_code)

    # Get base classes from "return_type" and add to template.base_classes
    try:
        return_type_instance = globals()[return_type]
        base_classes = get_base_classes(return_type_instance)
    except (KeyError, AttributeError) as err:
        raise HTTPException(
            status_code=400,
            detail={"error": type(err).__name__, "traceback": traceback.format_exc()},
        ) from err

    for base_class in base_classes:
        template.get("base_classes").append(base_class)

    return template


langchain_types_dict = build_langchain_types_dict()
