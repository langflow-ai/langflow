import json
import os
from uuid import UUID

import orjson
import pytest
from httpx import AsyncClient
from langflow.components.data.url import URLComponent
from langflow.components.input_output import ChatOutput
from langflow.components.logic import LoopComponent
from langflow.components.openai.openai_chat_model import OpenAIModelComponent
from langflow.components.processing import (
    ParserComponent,
    PromptComponent,
    SplitTextComponent,
    StructuredOutputComponent,
)
from langflow.graph import Graph
from langflow.memory import aget_messages
from langflow.schema.data import Data
from langflow.services.database.models.flow import FlowCreate

from tests.base import ComponentTestBaseWithClient
from tests.unit.build_utils import build_flow, get_build_events

TEXT = (
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet."
)


class TestLoopComponentWithAPI(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return LoopComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "data": [[Data(text="Hello World")]],
            "loop_input": [Data(text=TEXT)],
        }

    def test_latest_version(self, component_class, default_kwargs) -> None:
        """Test that the component works with the latest version."""
        result = component_class(**default_kwargs)
        assert result is not None, "Component returned None for the latest version."

    async def _create_flow(self, client, json_loop_test, logged_in_headers):
        vector_store = orjson.loads(json_loop_test)
        data = vector_store["data"]
        vector_store = FlowCreate(name="Flow", description="description", data=data, endpoint_name="f")
        response = await client.post("api/v1/flows/", json=vector_store.model_dump(), headers=logged_in_headers)
        response.raise_for_status()
        return response.json()["id"]

    async def check_messages(self, flow_id):
        messages = await aget_messages(flow_id=UUID(flow_id), order="ASC")
        assert len(messages) == 1
        assert messages[0].session_id == flow_id
        assert messages[0].sender == "Machine"
        assert messages[0].sender_name == "AI"
        assert len(messages[0].text) > 0
        return messages

    async def test_build_flow_loop(self, client, json_loop_test, logged_in_headers):
        """Test building a flow with a loop component."""
        # Create the flow
        flow_id = await self._create_flow(client, json_loop_test, logged_in_headers)

        # Start the build and get job_id
        build_response = await build_flow(client, flow_id, logged_in_headers)
        job_id = build_response["job_id"]
        assert job_id is not None

        # Get the events stream
        events_response = await get_build_events(client, job_id, logged_in_headers)
        assert events_response.status_code == 200

        # Process the events stream
        chat_output = None
        lines = []
        async for line in events_response.aiter_lines():
            if not line:  # Skip empty lines
                continue
            lines.append(line)
            if "ChatOutput" in line:
                chat_output = json.loads(line)
            # Process events if needed
            # We could add specific assertions here for loop-related events
        assert chat_output is not None
        messages = await self.check_messages(flow_id)
        ai_message = messages[0].text
        json_data = orjson.loads(ai_message)

        # Use a for loop for better debugging
        found = []
        json_data = [(data["text"], q_dict) for data, q_dict in json_data]
        for text, q_dict in json_data:
            expected_text = f"==> {q_dict['q']}"
            assert expected_text in text, (
                f"Found {found} until now, but expected '{expected_text}' not found in '{text}',"
                f"and the json_data is {json_data}"
            )
            found.append(expected_text)

    async def test_run_flow_loop(self, client: AsyncClient, created_api_key, json_loop_test, logged_in_headers):
        flow_id = await self._create_flow(client, json_loop_test, logged_in_headers)
        headers = {"x-api-key": created_api_key.api_key}
        payload = {
            "input_value": TEXT,
            "input_type": "chat",
            "session_id": f"{flow_id}run",
            "output_type": "chat",
            "tweaks": {},
        }
        response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)
        data = response.json()
        assert "outputs" in data
        assert "session_id" in data
        assert len(data["outputs"][-1]["outputs"]) > 0


@pytest.mark.skipif(os.getenv("OPENAI_API_KEY") is None, reason="OPENAI_API_KEY is not set")
def loop_flow():
    """Complete loop flow that processes multiple URLs through a loop."""
    # Create URL component to fetch content from multiple sources
    url_component = URLComponent()
    url_component.set(urls=["https://docs.langflow.org/"])

    # Create SplitText component to chunk the content
    split_text_component = SplitTextComponent()
    split_text_component.set(
        data_inputs=url_component.fetch_content,  # Verified: HandleInput name="data_inputs"
        chunk_size=1000,  # Verified: IntInput name="chunk_size"
        chunk_overlap=200,  # Verified: IntInput name="chunk_overlap"
        separator="\n\n",  # Verified: MessageTextInput name="separator"
    )

    # Create Loop component to iterate through the chunks
    loop_component = LoopComponent()
    loop_component.set(
        data=split_text_component.split_text  # Verified: HandleInput name="data"
    )

    # Create Parser component to format the current loop item
    parser_component = ParserComponent()
    parser_component.set(
        input_data=loop_component.item_output,  # Verified: HandleInput name="input_data"
        pattern="Content: {text}",  # Verified: MultilineInput name="pattern"
        sep="\n",  # Verified: MessageTextInput name="sep"
    )

    # Create Prompt component to create processing instructions
    prompt_component = PromptComponent()
    prompt_component.set(
        template="Analyze and summarize this content: {context}",  # Verified: PromptInput name="template"
        input_text=parser_component.parse_combined_text,  # Verified: str input name="input_text"
    )

    # Create OpenAI model component for processing
    openai_component = OpenAIModelComponent()
    openai_component.set(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="gpt-4.1-mini",  # Verified: DropdownInput name="model_name"
        temperature=0.7,  # Verified: SliderInput name="temperature"
    )

    # Create StructuredOutput component to process content
    structured_output = StructuredOutputComponent()
    structured_output.set(
        llm=openai_component.build_model,  # Verified: HandleInput name="llm"
        input_value=prompt_component.build_prompt,  # Verified: MultilineInput name="input_value"
        schema_name="ProcessedContent",  # Verified: MessageTextInput name="schema_name"
        system_prompt=(  # Added missing system_prompt - this was causing the "Multiple structured outputs" error
            "You are an AI that extracts one structured JSON object from unstructured text. "
            "Use a predefined schema with expected types (str, int, float, bool, dict). "
            "If multiple structures exist, extract only the first most complete one. "
            "Fill missing or ambiguous values with defaults: null for missing values. "
            "Ignore duplicates and partial repeats. "
            "Always return one valid JSON, never throw errors or return multiple objects."
            "Output: A single well-formed JSON object, and nothing else."
        ),
        output_schema=[  # Fixed schema types to match expected format
            {"name": "summary", "type": "str", "description": "Key summary of the content", "multiple": False},
            {"name": "topics", "type": "list", "description": "Main topics covered", "multiple": False},
            {"name": "source_url", "type": "str", "description": "Source URL of the content", "multiple": False},
        ],
    )

    # Connect the feedback loop - StructuredOutput back to Loop item input
    # Note: 'item' is a special dynamic input for LoopComponent feedback loops
    loop_component.set(item=structured_output.build_structured_output)

    # Create ChatOutput component to display final results
    chat_output = ChatOutput()
    chat_output.set(
        input_value=loop_component.done_output  # Verified: HandleInput name="input_value"
    )

    return Graph(start=url_component, end=chat_output)


async def test_loop_flow():
    """Test that loop_flow creates a working graph with proper loop feedback connection."""
    flow = loop_flow()
    assert flow is not None
    assert flow._start is not None
    assert flow._end is not None

    # Verify all expected components are present
    expected_vertices = {
        "URLComponent",
        "SplitTextComponent",
        "LoopComponent",
        "ParserComponent",
        "PromptComponent",
        "OpenAIModelComponent",
        "StructuredOutputComponent",
        "ChatOutput",
    }

    assert all(vertex.id.split("-")[0] in expected_vertices for vertex in flow.vertices)

    expected_execution_order = [
        "OpenAIModelComponent",
        "URLComponent",
        "SplitTextComponent",
        "LoopComponent",
        "ParserComponent",
        "PromptComponent",
        "StructuredOutputComponent",
        "LoopComponent",
        "ParserComponent",
        "PromptComponent",
        "StructuredOutputComponent",
        "LoopComponent",
        "ParserComponent",
        "PromptComponent",
        "StructuredOutputComponent",
        "LoopComponent",
        "ChatOutput",
    ]
    results = [result async for result in flow.async_start()]
    result_order = [result.vertex.id.split("-")[0] for result in results if hasattr(result, "vertex")]
    assert result_order == expected_execution_order
