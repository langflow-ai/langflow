import os

import pytest
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.output_parsers.OutputParser import OutputParserComponent
from langflow.components.prompts.Prompt import PromptComponent
from tests.integration.utils import ComponentInputHandle, run_single_component


@pytest.mark.asyncio
@pytest.mark.api_key_required
async def test_csv_output_parser_openai():
    format_instructions = ComponentInputHandle(
        clazz=OutputParserComponent,
        inputs={},
        output_name="format_instructions",
    )
    output_parser_handle = ComponentInputHandle(
        clazz=OutputParserComponent,
        inputs={},
        output_name="output_parser",
    )
    prompt_handler = ComponentInputHandle(
        clazz=PromptComponent,
        inputs={
            "template": "List the first five positive integers.\n\n{format_instructions}",  # noqa: RUF027
            "format_instructions": format_instructions,
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
    assert outputs["text_output"] == "1, 2, 3, 4, 5"
