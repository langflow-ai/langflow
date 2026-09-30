import sys
from copy import copy, deepcopy
from dataclasses import dataclass, field
from threading import Lock
from types import ModuleType
from typing import Any

from lfx.base.agents.crewai import crew as crew_module
from lfx.base.agents.crewai.crew import BaseCrewComponent
from lfx.components.crewai.sequential_crew import SequentialCrewComponent


@dataclass
class FakeAgent:
    role: str
    llm: Any
    tools: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    runtime_lock: Any = field(default_factory=Lock, compare=False)

    def copy(self):
        return FakeAgent(
            role=self.role,
            llm=copy(self.llm),
            tools=list(self.tools),
            metadata=deepcopy(self.metadata),
        )


@dataclass
class FakeTask:
    key: str
    agent: FakeAgent | None
    context: list["FakeTask"] | None = None
    tools: list[Any] = field(default_factory=list)

    def copy(self, agents: list[FakeAgent], task_mapping: dict[str, "FakeTask"]):
        copied_agent = None
        if self.agent is not None:
            copied_agent = next((agent for agent in agents if agent.role == self.agent.role), None)
        copied_context = None
        if isinstance(self.context, list):
            copied_context = [task_mapping[task.key] for task in self.context]
        copied_tools = list(self.tools)
        if not copied_tools and copied_agent is not None:
            copied_tools = list(copied_agent.tools)
        return FakeTask(
            key=self.key,
            agent=copied_agent,
            context=copied_context,
            tools=copied_tools,
        )


def test_get_tasks_and_agents_copies_shared_agents_and_rebinds_tasks(monkeypatch):
    original_llm = {"model": "gpt-4o"}
    original_tools = [{"name": "search"}]
    original_metadata = {"nested": {"enabled": True}}
    shared_agent = FakeAgent(
        role="researcher",
        llm=original_llm,
        tools=original_tools,
        metadata=original_metadata,
    )
    first_task = FakeTask(key="first", agent=shared_agent, tools=original_tools)
    second_task = FakeTask(key="second", agent=shared_agent, context=[first_task], tools=original_tools)
    original_tasks = [first_task, second_task]
    component = BaseCrewComponent(agents=[shared_agent, shared_agent], tasks=original_tasks)

    llm_calls = []
    tool_calls = []

    def convert_llm(llm):
        llm_calls.append(llm)
        return {"converted_llm": llm}

    def convert_tools(tools):
        tool_calls.append(tools)
        return [{"converted_tool": tool} for tool in tools]

    monkeypatch.setattr(crew_module, "convert_llm", convert_llm)
    monkeypatch.setattr(crew_module, "convert_tools", convert_tools)

    tasks, agents = component.get_tasks_and_agents()

    assert len(agents) == 1
    copied_agent = agents[0]
    assert copied_agent is not shared_agent
    assert shared_agent.llm is original_llm
    assert shared_agent.tools is original_tools
    assert shared_agent.metadata is original_metadata
    assert copied_agent.llm == {"converted_llm": original_llm}
    assert copied_agent.tools == [{"converted_tool": original_tools[0]}]
    assert copied_agent.metadata == original_metadata
    assert copied_agent.metadata is not original_metadata
    assert copied_agent.runtime_lock is not shared_agent.runtime_lock
    assert len(llm_calls) == 1
    assert len(tool_calls) == 1
    assert llm_calls[0] is not original_llm
    assert tool_calls[0] is not original_tools

    assert all(
        copied_task is not original_task for copied_task, original_task in zip(tasks, original_tasks, strict=True)
    )
    assert all(task.agent is copied_agent for task in tasks)
    assert all(task.agent is shared_agent for task in original_tasks)
    assert tasks[0].tools is not original_tasks[0].tools
    assert tasks[0].tools[0] is original_tasks[0].tools[0]
    assert tasks[1].context[0] is tasks[0]
    assert original_tasks[1].context[0] is original_tasks[0]


def test_get_tasks_and_agents_creates_fresh_copy_per_call_and_preserves_empty_list_fallback(monkeypatch):
    shared_agent = FakeAgent(role="researcher", llm={"model": "gpt-4o"}, tools=[{"name": "search"}])
    task = FakeTask(key="task", agent=shared_agent)
    component = BaseCrewComponent(agents=[shared_agent], tasks=[task])
    llm_calls = []
    tool_calls = []

    def convert_llm(llm):
        llm_calls.append(llm)
        return llm

    def convert_tools(tools):
        tool_calls.append(tools)
        return tools

    monkeypatch.setattr(crew_module, "convert_llm", convert_llm)
    monkeypatch.setattr(crew_module, "convert_tools", convert_tools)

    first_tasks, first_agents = component.get_tasks_and_agents(agents_list=[])
    second_tasks, second_agents = component.get_tasks_and_agents()

    assert first_agents[0] is not shared_agent
    assert second_agents[0] is not shared_agent
    assert first_agents[0] is not second_agents[0]
    assert first_tasks[0].agent is first_agents[0]
    assert second_tasks[0].agent is second_agents[0]
    assert task.agent is shared_agent
    assert len(llm_calls) == 2
    assert len(tool_calls) == 2
    assert shared_agent.llm == {"model": "gpt-4o"}
    assert shared_agent.tools == [{"name": "search"}]


def test_get_tasks_and_agents_copies_agentless_tasks(monkeypatch):
    agent = FakeAgent(role="manager", llm=None)
    agentless_task = FakeTask(key="task", agent=None, context=[])
    component = BaseCrewComponent(agents=[agent], tasks=[agentless_task])
    monkeypatch.setattr(crew_module, "convert_llm", lambda llm: llm)
    monkeypatch.setattr(crew_module, "convert_tools", lambda tools: tools)

    tasks, agents = component.get_tasks_and_agents()

    assert len(agents) == 1
    assert agents[0] is not agent
    assert tasks[0] is not agentless_task
    assert tasks[0].agent is None
    assert tasks[0].context == []


def test_get_tasks_and_agents_remaps_forward_task_context(monkeypatch):
    agent = FakeAgent(role="researcher", llm=None)
    later_task = FakeTask(key="later", agent=agent)
    earlier_task = FakeTask(key="earlier", agent=agent, context=[later_task])
    component = BaseCrewComponent(agents=[agent], tasks=[earlier_task, later_task])
    monkeypatch.setattr(crew_module, "convert_llm", lambda llm: llm)
    monkeypatch.setattr(crew_module, "convert_tools", lambda tools: tools)

    tasks, _ = component.get_tasks_and_agents()

    assert tasks[0].context[0] is tasks[1]
    assert earlier_task.context[0] is later_task


def test_get_tasks_and_agents_rebinds_equal_role_agents_by_identity(monkeypatch):
    first_agent = FakeAgent(role="researcher", llm=None, tools=["first-tool"])
    second_agent = FakeAgent(role="researcher", llm=None, tools=["second-tool"])
    component = SequentialCrewComponent(
        tasks=[
            FakeTask(key="first", agent=first_agent),
            FakeTask(key="second", agent=first_agent),
            FakeTask(key="third", agent=second_agent),
        ],
    )
    llm_calls = []
    tool_calls = []
    monkeypatch.setattr(crew_module, "convert_llm", lambda llm: llm_calls.append(llm) or llm)
    monkeypatch.setattr(crew_module, "convert_tools", lambda tools: tool_calls.append(tools) or tools)

    tasks, agents = component.get_tasks_and_agents()

    assert len(agents) == 2
    assert tasks[0].agent is agents[0]
    assert tasks[1].agent is agents[0]
    assert tasks[2].agent is agents[1]
    assert tasks[0].tools == ["first-tool"]
    assert tasks[1].tools == ["first-tool"]
    assert tasks[2].tools == ["second-tool"]
    assert len(llm_calls) == 2
    assert len(tool_calls) == 2


def test_sequential_crew_agents_deduplicates_by_identity_and_skips_none():
    shared_agent = FakeAgent(role="researcher", llm=None)
    equal_but_distinct_agent = FakeAgent(role="researcher", llm=None)
    component = SequentialCrewComponent(
        tasks=[
            FakeTask(key="first", agent=shared_agent),
            FakeTask(key="second", agent=shared_agent),
            FakeTask(key="third", agent=equal_but_distinct_agent),
            FakeTask(key="agentless", agent=None),
        ]
    )

    agents = component.agents

    assert len(agents) == 2
    assert agents[0] is shared_agent
    assert agents[1] is equal_but_distinct_agent


def test_convert_llm_preserves_crewai_base_llm(monkeypatch):
    fake_crewai = ModuleType("crewai")

    class BaseLLM:
        pass

    class LLM(BaseLLM):
        pass

    fake_crewai.BaseLLM = BaseLLM
    fake_crewai.LLM = LLM
    monkeypatch.setitem(sys.modules, "crewai", fake_crewai)
    llm = BaseLLM()

    assert crew_module.convert_llm(llm) is llm


def test_convert_tools_preserves_crewai_base_tools(monkeypatch):
    fake_base_tool_module = ModuleType("crewai.tools.base_tool")

    class BaseTool:
        pass

    class Tool(BaseTool):
        conversion_calls = 0

        @classmethod
        def from_langchain(cls, tool):
            cls.conversion_calls += 1
            converted = cls()
            converted.source = tool
            return converted

    fake_base_tool_module.BaseTool = BaseTool
    fake_base_tool_module.Tool = Tool
    monkeypatch.setitem(sys.modules, "crewai.tools.base_tool", fake_base_tool_module)
    crewai_tool = BaseTool()
    langchain_tool = object()

    converted = crew_module.convert_tools([crewai_tool, langchain_tool])
    converted_again = crew_module.convert_tools(converted)

    assert converted[0] is crewai_tool
    assert isinstance(converted[1], Tool)
    assert converted[1].source is langchain_tool
    assert converted_again[0] is converted[0]
    assert converted_again[1] is converted[1]
    assert Tool.conversion_calls == 1
