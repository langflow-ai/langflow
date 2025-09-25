import uuid
from typing import Any, Dict, List, Optional

import pytest
from pydantic import BaseModel, Field

from src.backend.base.langflow.custom.genesis.services.prompt.service import PromptService


class PromptData(BaseModel):
    name: str
    template: List[Any]
    commit_message: Optional[str] = ""
    tags: Optional[list[str]] = Field(default_factory=list)


class PromptVersionData(BaseModel):
    template: List[Any]
    commit_message: Optional[str] = ""
    version_metadata: Optional[Dict[str, str]] = Field(default=None)


@pytest.mark.asyncio
async def test_prompt_service_end_to_end():
    service = PromptService()

    prompt_name = f"TestPrompt-{uuid.uuid4()}"
    prompt_data = PromptData(
        name=prompt_name,
        template=[
            {
                "input_variables": ["content"],
                "role": "user",
                "content": {
                    "type": "text",
                    "text": "summarize the content: {{content}}",
                },
            }
        ],
        commit_message="Test prompt for E2E",
        tags=["e2e", "test"],
    )

    # ✅ DO NOT CALL .model_dump() here — let the service handle it

    create_response = await service.create_prompt(prompt_data.model_dump())
    assert create_response is not None
    assert create_response["name"] == prompt_name

    # List prompts
    prompts = await service.get_prompts()
    prompts = prompts["prompts"]

    prompt_names = [p["name"] for p in prompts]
    assert prompt_name in prompt_names
    prompt_id = next((p["_id"] for p in prompts if p["name"] == prompt_name), None)

    # Update prompt version
    updated_prompt_data = PromptVersionData(
        template=[
            {
                "input_variables": ["content"],
                "role": "user",
                "content": {
                    "type": "text",
                    "text": "summarize the content: {{content}}",
                },
            }
        ],
        commit_message="Updated Test prompt for E2E",
        version_metadata={"version_tag": "updated"},
    )

    update_response = await service.create_prompt_version(
        prompt_name, updated_prompt_data.model_dump()
    )
    assert update_response is not None
    assert update_response["version"] == 2

    # Simulate saving prompt in memory for formatting
    print("here", update_response)
    service._prompts[prompt_id] = update_response

    formatted = await service.format_prompt(prompt_id, content="some text to summarize")
    assert formatted == [
        {"content": "summarize the content: some text to summarize", "role": "user"}
    ]

    delete_response = await service.delete_prompt(prompt_name)
    assert delete_response.get("message", "") == "Prompt deleted successfully"

    remaining_prompts = await service.get_prompts()
    remaining_prompts = remaining_prompts["prompts"]
    remaining_prompts = [p["name"] for p in remaining_prompts]
    assert prompt_name not in remaining_prompts
