from httpx import AsyncClient, codes
from langflow_sdk import StreamChunk
from lfx.utils.constants import MESSAGE_SENDER_AI

from tests.unit.build_utils import create_flow


async def test_sdk_reads_chat_output_text_from_run_stream(
    client: AsyncClient, user_one_api_key: str, json_memory_chatbot_no_llm: str, logged_in_headers: dict[str, str]
) -> None:
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    input_text = "hello from the V1 run API"

    response = await client.post(
        f"/api/v1/run/{flow_id}",
        params={"stream": True},
        headers={"x-api-key": user_one_api_key},
        json={"input_value": input_text},
    )

    assert response.status_code == codes.OK, response.text
    chunks = [StreamChunk.model_validate_json(line) for line in response.iter_lines() if line]
    [output_message] = [
        chunk for chunk in chunks if chunk.event == "add_message" and chunk.data.get("sender") == MESSAGE_SENDER_AI
    ]
    assert f"User: {input_text}" in output_message.data["text"]
    assert output_message.text == output_message.data["text"]
