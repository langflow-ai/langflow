"""Dependency-free regression tests for CrewAI LLM conversion."""

import sys
from types import ModuleType

from lfx.base.agents.crewai.crew import convert_llm


def test_should_return_same_object_for_crewai_base_llm(monkeypatch):
    class FakeBaseLLM:
        pass

    class FakeLLM(FakeBaseLLM):
        pass

    class FakeProviderLLM(FakeBaseLLM):
        pass

    fake_crewai = ModuleType("crewai")
    fake_crewai.BaseLLM = FakeBaseLLM
    fake_crewai.LLM = FakeLLM
    monkeypatch.setitem(sys.modules, "crewai", fake_crewai)

    provider_llm = FakeProviderLLM()

    assert not isinstance(provider_llm, FakeLLM)
    assert convert_llm(provider_llm) is provider_llm
