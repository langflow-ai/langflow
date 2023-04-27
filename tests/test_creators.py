from typing import Dict, List

import pytest
from langflow.interface.agents.base import AgentCreator
from langflow.interface.base import LangChainTypeCreator


@pytest.fixture
def sample_lang_chain_type_creator() -> LangChainTypeCreator:
    class SampleLangChainTypeCreator(LangChainTypeCreator):
        type_name: str = "test_type"

        def type_to_loader_dict(self) -> Dict:  # type: ignore
            return {"test_type": "TestClass"}

        def to_list(self) -> List[str]:
            return ["node1", "node2"]

        def get_signature(self, name: str) -> Dict:
            return {
                "template": {"test_field": {"type": "str"}},
                "description": "test description",
                "base_classes": ["base_class1", "base_class2"],
            }

    return SampleLangChainTypeCreator()


@pytest.fixture
def sample_agent_creator() -> AgentCreator:
    return AgentCreator()


def test_lang_chain_type_creator_to_dict(
    sample_lang_chain_type_creator: LangChainTypeCreator,
):
    type_dict = sample_lang_chain_type_creator.to_dict()
    assert len(type_dict) == 1
    assert "test_type" in type_dict
    assert "node1" in type_dict["test_type"]
    assert "node2" in type_dict["test_type"]
    assert "template" in type_dict["test_type"]["node1"]
    assert "description" in type_dict["test_type"]["node1"]
    assert "base_classes" in type_dict["test_type"]["node1"]


def test_agent_creator_type_to_loader_dict(sample_agent_creator: AgentCreator):
    type_to_loader_dict = sample_agent_creator.type_to_loader_dict
    assert len(type_to_loader_dict) > 0
    assert "JsonAgent"
