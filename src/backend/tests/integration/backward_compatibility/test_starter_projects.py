import pytest
from langflow.schema.message import Message

from tests.api_keys import get_openai_api_key
from tests.integration.utils import download_flow_from_github, run_json_flow


@pytest.mark.api_key_required
async def test_1_0_15_basic_prompting():
    api_key = get_openai_api_key()
    json_flow = download_flow_from_github("Basic Prompting (Hello, World)", "1.0.15")
    json_flow.set_value(json_flow.get_component_by_type("OpenAIModel"), "api_key", api_key)
    outputs = await run_json_flow(json_flow, run_input="my name is bob, say hello!")
    assert isinstance(outputs["message"], Message)
    response = outputs["message"].text.lower()
    assert "arr" in response or "ahoy" in response
