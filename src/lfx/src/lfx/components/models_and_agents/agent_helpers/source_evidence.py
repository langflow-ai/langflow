"""Checkpoint source evidence before compaction can remove its tool message."""

from typing import Annotated

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import OmitFromInput
from langchain_core.messages import ToolMessage
from typing_extensions import NotRequired

from lfx.projects.artifacts import SOURCE_EVIDENCE_KIND, CollectedEvidence, SourceRecord, SourceUse

EVIDENCE_STATE_KEY = "harness_source_evidence"


class SourceEvidenceState(AgentState):
    harness_source_evidence: NotRequired[Annotated[dict, OmitFromInput]]


def collect_tool_evidence(messages, previous: CollectedEvidence) -> CollectedEvidence:
    sources = {source.id: source for source in previous.sources}
    uses = dict.fromkeys(previous.uses)
    for message in messages:
        if not isinstance(message, ToolMessage) or message.status == "error":
            continue
        # Only the structured result of a completed tool is evidence. Never parse
        # model prose, tool arguments, or a JSON-looking string in fetched content.
        artifact = message.artifact
        outputs = artifact if isinstance(artifact, list) else [artifact]
        for item in outputs:
            output = item
            # Run Flow preserves a component's output-inspector envelope. Its
            # raw object is the result; repr is presentation text, never evidence.
            if isinstance(output, dict) and output.get("type") == "object" and {"raw", "repr"} <= output.keys():
                output = output["raw"]
            if not isinstance(output, dict) or output.get("kind") != SOURCE_EVIDENCE_KIND:
                continue
            source = SourceRecord.model_validate(output.get("source"))
            sources.setdefault(source.id, source)
            uses[SourceUse(source_id=source.id, tool_call_id=message.tool_call_id, tool_name=message.name)] = None
    return CollectedEvidence(sources=tuple(sources.values()), uses=tuple(uses))


class SourceEvidenceMiddleware(AgentMiddleware):
    state_schema = SourceEvidenceState

    def _collect(self, state):
        previous = CollectedEvidence.model_validate(state.get(EVIDENCE_STATE_KEY) or {})
        evidence = collect_tool_evidence(state["messages"], previous)
        return {EVIDENCE_STATE_KEY: evidence.model_dump(mode="json")} if evidence != previous else None

    def before_model(self, state, runtime):  # noqa: ARG002
        return self._collect(state)

    async def abefore_model(self, state, runtime):  # noqa: ARG002
        return self._collect(state)

    def after_agent(self, state, runtime):  # noqa: ARG002
        # return_direct tools can finish without another model call.
        return self._collect(state)

    async def aafter_agent(self, state, runtime):  # noqa: ARG002
        return self._collect(state)
