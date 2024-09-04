from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.output_parsers.CSVOutputParser import CSVOutputParserComponent
from langflow.components.prompts.Prompt import PromptComponent
from langflow.schema.message import Message
from langflow.template.field.base import Input
from langflow.template.template.base import Template
from tests.integration.utils import ComponentInputHandle, run_single_component

import pytest


@pytest.mark.asyncio
@pytest.mark.api_key_required
@pytest.mark.skip(reason="template field not validating correctly")
async def test_csv_output_parser_openai():
    import os

    sample_template_field = Input(name="test_field", field_type="str", value="list first three positive integers")
    template = Template(type_name="test_template", fields=[sample_template_field])

    output_parser_handle = ComponentInputHandle(
        clazz=CSVOutputParserComponent,
        inputs={},
        output_name="output_parser",
    )
    prompt_handler = ComponentInputHandle(
        clazz=PromptComponent,
        inputs={
            "template": template,
            "format_instructions": CSVOutputParserComponent().format_instructions(),
        },
        output_name="prompt",
    )

    outputs = await run_single_component(
        OpenAIModelComponent,
        inputs={
            "api_key": os.environ["OPENAI_API_KEY"],
            "output_parser": output_parser_handle,
            "input_value": prompt_handler,
        },
    )
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "1,2,3"
