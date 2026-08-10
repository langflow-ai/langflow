"""Tests for CrewAI LLM conversion across supported crewai versions.

Regression coverage for LE-2092: with crewai >= 1.0, ``crewai.LLM(...)`` is a
factory that returns provider-specific subclasses of ``BaseLLM`` (for example
``OpenAICompletion``) which are *not* instances of ``crewai.LLM``. A guard that
tests ``isinstance(llm, LLM)`` therefore stops being idempotent, and the second
conversion pass performed by ``BaseCrewComponent.get_tasks_and_agents`` falls
through to the LangChain branch and raises
``AttributeError: 'OpenAICompletion' object has no attribute 'get_lc_namespace'``.

crewai is an optional dependency that is not installable in the default
workspace (documented httpx conflict), so these tests skip when it is absent.
They were run against crewai 0.126.0, 0.134.0 and 1.15.10.
"""

import pytest

pytest.importorskip("crewai", reason="crewai is an optional dependency")

from crewai import BaseLLM
from lfx.base.agents.crewai.crew import convert_llm

API_KEY = "sk-component-level-key"
MODEL_NAME = "gpt-4o-mini"


@pytest.fixture
def langchain_model():
    langchain_openai = pytest.importorskip("langchain_openai")
    return langchain_openai.ChatOpenAI(model=MODEL_NAME, api_key=API_KEY)


def test_should_build_crewai_llm_when_given_langchain_model(langchain_model):
    # Act
    converted = convert_llm(langchain_model)

    # Assert
    assert isinstance(converted, BaseLLM)
    assert converted.api_key == API_KEY


def test_should_return_same_object_when_llm_is_already_crewai_native(langchain_model):
    """The crew re-converts every agent LLM, so conversion must be idempotent."""
    # Arrange
    converted = convert_llm(langchain_model)

    # Act
    reconverted = convert_llm(converted)

    # Assert
    assert reconverted is converted
    assert reconverted.api_key == API_KEY


def test_should_preserve_agent_llm_when_crew_reconverts_it(langchain_model):
    """Reproduces the Sequential Task Agent -> Sequential Crew failure path."""
    # Arrange
    from crewai import Agent
    from lfx.components.crewai.sequential_crew import SequentialCrewComponent

    agent = Agent(
        role="Researcher",
        goal="Research the topic",
        backstory="An experienced researcher",
        llm=convert_llm(langchain_model),
    )
    crew_component = SequentialCrewComponent()

    # Act
    _tasks, agents = crew_component.get_tasks_and_agents(agents_list=[agent])

    # Assert
    assert isinstance(agents[0].llm, BaseLLM)
    assert agents[0].llm.api_key == API_KEY


def test_should_return_none_when_llm_is_missing():
    assert convert_llm(None) is None
