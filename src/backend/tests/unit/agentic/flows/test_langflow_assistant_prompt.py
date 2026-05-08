"""Tests for the LangflowAssistant.json parent agent system prompt.

Regression guard: when a FileSystemTool is wired into the parent Agent,
the prompt must teach the agent (a) that the tool exists and (b) that
using it for legitimate file creation is allowed and not blocked by the
generic Code Safety rule (which applies to GENERATED component code).
"""

import json
from pathlib import Path

import pytest

LANGFLOW_ASSISTANT_JSON = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "base"
    / "langflow"
    / "agentic"
    / "flows"
    / "LangflowAssistant.json"
)
PARENT_AGENT_ID = "Agent-6Fady"


@pytest.fixture(scope="module")
def parent_agent_prompt() -> str:
    flow = json.loads(LANGFLOW_ASSISTANT_JSON.read_text(encoding="utf-8"))
    for node in flow["data"]["nodes"]:
        node_data = node["data"]
        if node_data.get("type") == "Agent" and node_data.get("id") == PARENT_AGENT_ID:
            return node_data["node"]["template"]["system_prompt"]["value"]
    msg = f"Parent agent {PARENT_AGENT_ID} not found in LangflowAssistant.json"
    raise AssertionError(msg)


class TestParentAgentFileSystemCapability:
    def test_should_mention_file_system_tool_capability(self, parent_agent_prompt: str):
        prompt_lower = parent_agent_prompt.lower()
        assert "file system" in prompt_lower, "Parent prompt must mention File System tool capability"

    def test_should_mention_write_file_operation(self, parent_agent_prompt: str):
        # The agent must know it can create files via the tool, not just refuse.
        assert "write_file" in parent_agent_prompt, (
            "Parent prompt must reference the write_file operation so the agent knows it CAN create files"
        )

    def test_should_clarify_code_safety_applies_to_generated_component_code(
        self, parent_agent_prompt: str
    ):
        # The Code Safety rule must scope its file-operations ban to GENERATED
        # component source code — otherwise the agent over-generalizes and
        # refuses legitimate File System tool calls (write_file/edit_file).
        prompt_lower = parent_agent_prompt.lower()
        assert "generated component code" in prompt_lower or "generated component source" in prompt_lower, (
            "Code Safety rule must explicitly scope its file-operation ban to "
            "generated component code so the agent does not refuse legitimate "
            "File System tool calls."
        )

    def test_should_state_file_system_use_is_allowed_for_user_files(
        self, parent_agent_prompt: str
    ):
        prompt_lower = parent_agent_prompt.lower()
        # Some phrasing that authorizes file writes via the tool when the user
        # asks for a file (README, instructions, etc).
        assert "use the file system tool" in prompt_lower or "use write_file" in prompt_lower, (
            "Parent prompt must affirmatively instruct the agent to use the File System tool "
            "when the user asks to create files."
        )
