from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import patch

from lfx.services import deps

sys.modules.setdefault("litellm", SimpleNamespace(exceptions=SimpleNamespace(BadRequestError=Exception)))
deps.get_settings_service = lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True))


@dataclass
class FakeAgent:
    role: str
    llm: object = None
    tools: list = field(default_factory=list)


@dataclass
class FakeTask:
    description: str
    agent: FakeAgent


@dataclass
class FakeCrew:
    agents: list
    tasks: list
    manager_agent: FakeAgent | None = None
    kwargs: dict = field(default_factory=dict)

    def __init__(self, **kwargs):
        self.agents = kwargs["agents"]
        self.tasks = kwargs["tasks"]
        self.manager_agent = kwargs.get("manager_agent")
        self.kwargs = kwargs


@dataclass
class FakeLLM:
    model: str
    api_key: str | None = None
    api_base: str | None = None
    extra: dict = field(default_factory=dict)

    def __init__(self, model, api_key=None, api_base=None, **kwargs):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.extra = kwargs


class FakeToolAdapter:
    @staticmethod
    def from_langchain(tool):
        return {"tool": tool}


def _fake_crewai_module():
    fake_tool_module = SimpleNamespace(Tool=FakeToolAdapter)
    fake_task_module = SimpleNamespace(TaskOutput=type("TaskOutput", (), {}))
    sys.modules["crewai.tools"] = SimpleNamespace(base_tool=fake_tool_module)
    sys.modules["crewai.tools.base_tool"] = fake_tool_module
    sys.modules["crewai.task"] = fake_task_module
    return SimpleNamespace(
        Crew=FakeCrew,
        LLM=FakeLLM,
        Process=SimpleNamespace(sequential="sequential", hierarchical="hierarchical"),
    )


def _load_crewai_components():
    sys.modules.setdefault("litellm", SimpleNamespace(exceptions=SimpleNamespace(BadRequestError=Exception)))

    hierarchical_module = importlib.import_module("lfx.components.crewai.hierarchical_crew")
    sequential_module = importlib.import_module("lfx.components.crewai.sequential_crew")
    return hierarchical_module.HierarchicalCrewComponent, sequential_module.SequentialCrewComponent


def test_sequential_build_crew_returns_fresh_agents_and_tasks():
    _, sequential_crew_component = _load_crewai_components()
    task_agent = FakeAgent(role="researcher", llm=None, tools=["tool-a"])
    task = FakeTask(description="answer", agent=task_agent)
    component = sequential_crew_component()
    component.tasks = [task]
    component.memory = True
    component.use_cache = True
    component.max_rpm = 10
    component.share_crew = False
    component.function_calling_llm = None
    component.verbose = 0

    with patch.dict(sys.modules, {"crewai": _fake_crewai_module()}):
        crew_one = component.build_crew()
        crew_two = component.build_crew()

    assert crew_one is not crew_two
    assert crew_one.agents[0] is not crew_two.agents[0]
    assert crew_one.tasks[0] is not crew_two.tasks[0]
    assert crew_one.tasks[0].agent is crew_one.agents[0]
    assert crew_two.tasks[0].agent is crew_two.agents[0]

    crew_one.agents[0].tools.append("tool-b")
    crew_one.tasks[0].description = "changed"

    assert crew_two.agents[0].tools == [{"tool": "tool-a"}]
    assert crew_two.tasks[0].description == "answer"


def test_hierarchical_build_crew_returns_fresh_manager_agent():
    hierarchical_crew_component, _ = _load_crewai_components()
    worker = FakeAgent(role="worker", llm=None, tools=["tool-a"])
    manager = FakeAgent(role="manager", llm=None, tools=["tool-b"])
    task = FakeTask(description="plan", agent=worker)
    component = hierarchical_crew_component()
    component.agents = [worker]
    component.tasks = [task]
    component.manager_agent = manager
    component.manager_llm = None
    component.memory = False
    component.use_cache = True
    component.max_rpm = 10
    component.share_crew = False
    component.function_calling_llm = None
    component.verbose = 0

    with patch.dict(sys.modules, {"crewai": _fake_crewai_module()}):
        crew_one = component.build_crew()
        crew_two = component.build_crew()

    assert crew_one.manager_agent is not crew_two.manager_agent
    assert crew_one.manager_agent is not manager

    crew_one.manager_agent.tools.append("tool-c")

    assert crew_two.manager_agent.tools == [{"tool": "tool-b"}]
    assert manager.tools == ["tool-b"]
