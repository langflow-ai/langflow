"""Saved Knowledge nodes must report their application requirements in standalone lfx."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from lfx.components.files_and_knowledge.retrieval import KnowledgeBaseComponent


@pytest.mark.asyncio
async def test_retrieval_requires_a_user_before_opening_application_services():
    component = KnowledgeBaseComponent(knowledge_base="saved_knowledge", _user_id=None)
    component._vertex = SimpleNamespace(graph=SimpleNamespace(user_id=None))

    with pytest.raises(ValueError, match="User ID is required"):
        await component.retrieve_data()


@pytest.mark.asyncio
async def test_retrieval_requires_langflow_application_services():
    component = KnowledgeBaseComponent(knowledge_base="saved_knowledge", _user_id=uuid4())

    with pytest.raises(RuntimeError, match="requires Langflow's application services"):
        await component.retrieve_data()
