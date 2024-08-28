import json

import pytest
from langflow.schema.message import Message
from tests.api_keys import get_openai_api_key
from tests.integration.utils import run_flow, download_flow_from_github, run_json_flow


@pytest.mark.asyncio
@pytest.mark.api_key_required
async def test_1_0_15_basic_prompting():
    api_key = get_openai_api_key()
    json_flow = download_flow_from_github("Basic Prompting (Hello, World)", "1.0.15")
    json_flow.set_value(json_flow.get_component_by_type("OpenAIModel"), "api_key", api_key)
    outputs = await run_json_flow(json_flow, run_input="hello!")
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "This is the message: hello!"
