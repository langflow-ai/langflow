"""Load reviewed skills on demand and enforce their tool scope at execution."""

from typing import Annotated

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import OmitFromInput
from langchain_core.callbacks.manager import adispatch_custom_event, dispatch_custom_event
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import NotRequired

from lfx.components.models_and_agents.agent_helpers.harness_middleware import HARNESS_EVENT
from lfx.projects.skills import HarnessSkills

ACTIVATE_SKILL = "activate_skill"
FINISH_SKILL = "finish_skill"
ACTIVE_SKILL = "harness_active_skill"


class SkillState(AgentState):
    harness_active_skill: NotRequired[Annotated[dict | None, OmitFromInput]]


class ActivateSkillArgs(BaseModel):
    skill: str = Field(description="The exact skill identifier from the available skills list.")


class FinishSkillArgs(BaseModel):
    pass


class HarnessSkillMiddleware(AgentMiddleware):
    state_schema = SkillState

    def __init__(self, configuration: HarnessSkills, tools):
        self.skills = {
            f"{pack.reference.project_id}:{skill.name}": (pack, skill)
            for pack in configuration.packs
            for skill in pack.skills
        }
        if any(tool.name in {ACTIVATE_SKILL, FINISH_SKILL} for tool in tools):
            msg = "Rename tools named activate_skill or finish_skill before attaching Skill Packs."
            raise ValueError(msg)
        global_packs = {str(value) for value in configuration.global_tool_pack_ids}
        scoped_packs = {
            str(ref.project_id) for _, skill in self.skills.values() for ref in skill.tool_packs
        } - global_packs
        self.tool_packs = {}
        for tool in tools:
            binding = (tool.metadata or {}).get("harness_tool_pack")
            if binding and binding["reference"]["project_id"] in scoped_packs:
                self.tool_packs[tool.name] = binding["reference"]["project_id"]
        self.tools = [
            StructuredTool.from_function(
                func=lambda skill: skill,
                name=ACTIVATE_SKILL,
                description="Activate one skill to load its instructions and enable its tools. Call this alone.",
                args_schema=ActivateSkillArgs,
            ),
            StructuredTool.from_function(
                func=lambda: "Skill finished",
                name=FINISH_SKILL,
                description="Finish the active skill and disable its scoped tools. Call this alone.",
                args_schema=FinishSkillArgs,
            ),
        ]

    def _active(self, state):
        active = state.get(ACTIVE_SKILL)
        if not active:
            return None
        entry = self.skills.get(active.get("key"))
        if entry is None or entry[0].reference.revision != active.get("revision"):
            msg = "The active skill no longer matches this run's reviewed configuration."
            raise ValueError(msg)
        return entry

    def _allowed(self, name, state):
        if name not in self.tool_packs:
            return True
        active = self._active(state)
        return bool(active and self.tool_packs[name] in {str(ref.project_id) for ref in active[1].tool_packs})

    def _prepare(self, request):
        active = self._active(request.state)
        lines = [
            "Available skills (activate one before using it; finish it when done):",
            *[
                f"- {key}: {pack.name} / {skill.name}: {skill.description}"
                for key, (pack, skill) in self.skills.items()
            ],
        ]
        if active:
            pack, skill = active
            lines.extend([f"Active skill: {pack.name} / {skill.name}", skill.instructions])
        original = request.system_message.content if request.system_message else ""
        content = list(original) if isinstance(original, list) else [{"type": "text", "text": original}]
        content.append({"type": "text", "text": "\n\n".join(lines)})
        return request.override(
            system_message=SystemMessage(content=content),
            tools=[
                tool
                for tool in request.tools
                if self._allowed(tool.name if hasattr(tool, "name") else tool.get("name"), request.state)
            ],
        )

    def wrap_model_call(self, request, handler):
        return handler(self._prepare(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._prepare(request))

    @staticmethod
    def _message(request, content, *, error=False):
        return ToolMessage(
            content=content,
            name=request.tool_call["name"],
            tool_call_id=request.tool_call["id"],
            status="error" if error else "success",
        )

    def _control(self, request):
        call = request.tool_call
        if call["name"] not in {ACTIVATE_SKILL, FINISH_SKILL}:
            if not self._allowed(call["name"], request.state):
                return self._message(
                    request,
                    "This tool requires an active skill that includes it. Activate that skill first.",
                    error=True,
                ), {"kind": "skill_tool_blocked", "tool_name": call["name"]}
            return None, None
        last = next((m for m in reversed(request.state["messages"]) if isinstance(m, AIMessage)), None)
        if last is None or len(last.tool_calls) != 1:
            return self._message(
                request, "Activate or finish a skill in a separate turn before calling other tools.", error=True
            ), None
        if call["name"] == FINISH_SKILL:
            active = None
            evidence = {"kind": "skill_finished"}
            content = "Skill finished. Its scoped tools are now disabled."
        else:
            key = call["args"].get("skill")
            if not isinstance(key, str) or key not in self.skills:
                return self._message(
                    request, "Choose an exact identifier from the available skills list.", error=True
                ), None
            pack, skill = self.skills[key]
            active = {"key": key, "revision": pack.reference.revision}
            evidence = {
                "kind": "skill_activated",
                "skill": skill.name,
                "pack": pack.name,
                **pack.reference.model_dump(mode="json"),
            }
            content = f"Activated {skill.name}. Follow the active skill instructions in the system message."
        return Command(update={ACTIVE_SKILL: active, "messages": [self._message(request, content)]}), evidence

    def wrap_tool_call(self, request, handler):
        result, evidence = self._control(request)
        if evidence:
            dispatch_custom_event(HARNESS_EVENT, {**evidence, "tool_call_id": request.tool_call["id"]})
        return result if result is not None else handler(request)

    async def awrap_tool_call(self, request, handler):
        result, evidence = self._control(request)
        if evidence:
            await adispatch_custom_event(HARNESS_EVENT, {**evidence, "tool_call_id": request.tool_call["id"]})
        return result if result is not None else await handler(request)
