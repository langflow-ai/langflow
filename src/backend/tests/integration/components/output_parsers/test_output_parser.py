import os

import pytest
from langflow.components.helpers import OutputParserComponent
from langflow.components.languagemodels import OpenAIModelComponent
from langflow.components.processing import PromptComponent

from tests.integration.utils import ComponentInputHandle, run_single_component


@pytest.mark.api_key_required
async def test_csv_output_parser_openai():
    format_instructions_ = ComponentInputHandle(
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
            "template": "List the first five positive integers.\n\n{format_instructions}",
            "format_instructions": format_instructions_,
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
