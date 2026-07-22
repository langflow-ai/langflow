"""Tests for the Amazon Bedrock Knowledge Base Retriever Langflow component."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock langflow and langchain_aws modules before importing the component
mock_langflow = types.ModuleType("langflow")
mock_langflow.__path__ = []
mock_langflow_custom = types.ModuleType("langflow.custom")
mock_langflow_io = types.ModuleType("langflow.io")
mock_langflow_schema = types.ModuleType("langflow.schema")


class MockComponent:
    """Mock Component base class."""


mock_langflow_custom.Component = MockComponent


class MockInput:
    """Mock IO input class."""

    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


mock_langflow_io.DropdownInput = MockInput
mock_langflow_io.IntInput = MockInput
mock_langflow_io.MessageTextInput = MockInput
mock_langflow_io.Output = MockInput
mock_langflow_io.SecretStrInput = MockInput


class MockData:
    """Mock Data class."""

    def __init__(self, text: str = "", data: dict | None = None) -> None:
        self.text = text
        self.data = data or {}


mock_langflow_schema.Data = MockData

# Register all mock modules
sys.modules["langflow"] = mock_langflow
sys.modules["langflow.custom"] = mock_langflow_custom
sys.modules["langflow.io"] = mock_langflow_io
sys.modules["langflow.schema"] = mock_langflow_schema

# Import component via relative path
_component_path = (
    Path(__file__).resolve().parents[4] / "src" / "lfx" / "components" / "aws" / "bedrock_knowledge_base_retriever.py"
)
spec = importlib.util.spec_from_file_location("bedrock_knowledge_base_retriever", _component_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
BedrockKnowledgeBaseRetrieverComponent = mod.BedrockKnowledgeBaseRetrieverComponent


@patch("langchain_aws.retrievers.AmazonKnowledgeBasesRetriever")
def test_retrieve_with_managed_config(mock_retriever_class: MagicMock) -> None:
    """Test retrieval uses langchain-aws retriever with managed config."""
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = [
        MagicMock(page_content="Document 1", metadata={"source": "s3://b/1", "score": 0.9}),
        MagicMock(page_content="Document 2", metadata={"source": "s3://b/2", "score": 0.8}),
    ]
    mock_retriever_class.return_value = mock_retriever

    component = BedrockKnowledgeBaseRetrieverComponent()
    component.knowledge_base_id = "TEST123456"
    component.query = "What is managed KB?"
    component.region_name = "us-west-2"
    component.number_of_results = 5
    component.aws_access_key_id = ""
    component.aws_secret_access_key = ""

    results = component.retrieve()

    mock_retriever_class.assert_called_once()
    call_kwargs = mock_retriever_class.call_args.kwargs
    assert call_kwargs["knowledge_base_id"] == "TEST123456"
    assert "managedSearchConfiguration" in call_kwargs["retrieval_config"]
    assert len(results) == 2
    assert results[0].text == "Document 1"


@patch("langchain_aws.retrievers.AmazonKnowledgeBasesRetriever")
def test_retrieve_with_credentials(mock_retriever_class: MagicMock) -> None:
    """Test credentials are passed when provided."""
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = []
    mock_retriever_class.return_value = mock_retriever

    component = BedrockKnowledgeBaseRetrieverComponent()
    component.knowledge_base_id = "TEST123456"
    component.query = "test"
    component.region_name = "us-east-1"
    component.number_of_results = 5
    component.aws_access_key_id = "AKID123"
    component.aws_secret_access_key = "SECRET456"  # noqa: S105

    component.retrieve()

    call_kwargs = mock_retriever_class.call_args.kwargs
    assert call_kwargs["aws_access_key_id"] == "AKID123"
    assert call_kwargs["aws_secret_access_key"] == "SECRET456"  # noqa: S105
