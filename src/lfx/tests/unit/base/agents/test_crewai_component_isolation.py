from __future__ import annotations

import sys
from dataclasses import dataclass, field
from threading import Lock
from types import ModuleType, SimpleNamespace

import pytest
from lfx.components.crewai.hierarchical_crew import HierarchicalCrewComponent
from lfx.components.crewai.sequential_crew import SequentialCrewComponent


@dataclass
class FakeAgent:
    role: str
    llm: object = None
    tools: list = field(default_factory=list)
    runtime_lock: object = field(default_factory=Lock, repr=False, compare=False)

    def copy(self):
        return type(self)(role=self.role, llm=self.llm, tools=list(self.tools))


@dataclass
class FakeTask:
    description: str
    agent: FakeAgent | None
    context: list[FakeTask] | None = None
    tools: list = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.description

    def copy(self, agents, task_mapping):
        copied_agent = next((agent for agent in agents if self.agent and agent.role == self.agent.role), None)
        copied_context = (
            [task_mapping[context_task.key] for context_task in self.context]
            if isinstance(self.context, list)
            else None
        )
        return type(self)(
            description=self.description,
            agent=copied_agent,
            context=copied_context,
            tools=list(self.tools),
        )


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


@pytest.fixture
def fake_crewai(monkeypatch):
    fake_base_llm = type("BaseLLM", (), {})
    fake_base_tool = type("BaseTool", (), {})
    crewai_module = ModuleType("crewai")
    crewai_module.__path__ = []
    crewai_module.Crew = FakeCrew
    crewai_module.BaseLLM = fake_base_llm
    crewai_module.LLM = FakeLLM
    crewai_module.Process = SimpleNamespace(sequential="sequential", hierarchical="hierarchical")

    tools_module = ModuleType("crewai.tools")
    tools_module.__path__ = []
    base_tool_module = ModuleType("crewai.tools.base_tool")
    base_tool_module.BaseTool = fake_base_tool
    base_tool_module.Tool = FakeToolAdapter
    task_module = ModuleType("crewai.task")
    task_module.TaskOutput = type("TaskOutput", (), {})

    monkeypatch.setitem(sys.modules, "crewai", crewai_module)
    monkeypatch.setitem(sys.modules, "crewai.tools", tools_module)
    monkeypatch.setitem(sys.modules, "crewai.tools.base_tool", base_tool_module)
    monkeypatch.setitem(sys.modules, "crewai.task", task_module)


def test_sequential_build_crew_returns_fresh_agents_and_tasks(fake_crewai):  # noqa: ARG001
    agent = FakeAgent(role="researcher", tools=["tool-a"])
    same_role_agent = FakeAgent(role="researcher", tools=["tool-c"])
    first_task = FakeTask(description="research", agent=agent)
    second_task = FakeTask(description="answer", agent=agent, context=[first_task])
    third_task = FakeTask(description="review", agent=same_role_agent, context=[second_task])
    component = SequentialCrewComponent()
    component.tasks = [first_task, second_task, third_task]
    component.memory = True
    component.use_cache = True
    component.max_rpm = 10
    component.share_crew = False
    component.function_calling_llm = None
    component.verbose = 0

    crew_one = component.build_crew()
    crew_two = component.build_crew()

    assert len(crew_one.agents) == 2
    assert crew_one.agents[0] is not crew_one.agents[1]
    assert crew_one.agents[0] is not crew_two.agents[0]
    assert crew_one.tasks[0] is not crew_two.tasks[0]
    assert crew_one.tasks[0].agent is crew_one.agents[0]
    assert crew_one.tasks[1].agent is crew_one.agents[0]
    assert crew_one.tasks[2].agent is crew_one.agents[1]
    assert crew_one.tasks[1].context == [crew_one.tasks[0]]
    assert crew_one.tasks[2].context == [crew_one.tasks[1]]
    assert crew_two.tasks[1].context == [crew_two.tasks[0]]

    crew_one.agents[0].tools.append("tool-b")
    crew_one.tasks[0].description = "changed"

    assert crew_two.agents[0].tools == [{"tool": "tool-a"}]
    assert crew_two.tasks[0].description == "research"
    assert agent.tools == ["tool-a"]
    assert first_task.agent is agent
    assert second_task.context == [first_task]


def test_hierarchical_build_crew_returns_fresh_manager_agent(fake_crewai):  # noqa: ARG001
    worker = FakeAgent(role="worker", tools=["tool-a"])
    manager = FakeAgent(role="manager", tools=["tool-b"])
    task = FakeTask(description="plan", agent=worker)
    component = HierarchicalCrewComponent()
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

    crew_one = component.build_crew()
    crew_two = component.build_crew()

    assert crew_one.manager_agent is not crew_two.manager_agent
    assert crew_one.manager_agent is not manager

    crew_one.manager_agent.tools.append("tool-c")

    assert crew_two.manager_agent.tools == [{"tool": "tool-b"}]
    assert manager.tools == ["tool-b"]


def test_real_crewai_agent_with_rpm_lock_can_be_copied(monkeypatch):
    crewai = pytest.importorskip("crewai", reason="crewai is an optional dependency")
    monkeypatch.setattr("lfx.base.agents.crewai.crew.convert_llm", lambda llm: llm)
    monkeypatch.setattr("lfx.base.agents.crewai.crew.convert_tools", lambda tools: list(tools or []))

    agent = crewai.Agent(
        role="researcher",
        goal="research",
        backstory="researcher",
        llm="gpt-4o-mini",
        max_rpm=7,
    )
    task = crewai.Task(description="answer", expected_output="answer", agent=agent)
    component = SequentialCrewComponent()
    component.tasks = [task]
    component.memory = False
    component.use_cache = True
    component.max_rpm = 10
    component.share_crew = False
    component.function_calling_llm = None
    component.verbose = 0

    crew_one = component.build_crew()
    crew_two = component.build_crew()

    assert crew_one.agents[0] is not crew_two.agents[0]
    assert crew_one.agents[0] is not agent
    assert crew_one.tasks[0].agent is crew_one.agents[0]
    assert crew_two.tasks[0].agent is crew_two.agents[0]
    assert crew_one.agents[0].max_rpm == 7
