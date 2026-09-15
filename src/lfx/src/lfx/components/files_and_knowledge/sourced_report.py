from lfx.custom import Component
from lfx.io import BoolInput, DataInput, MessageInput, Output, StrInput
from lfx.projects.artifacts import (
    AgentRunResult,
    ArtifactExecution,
    CollectedEvidence,
    SourcedReport,
    SourceRecord,
    store_report,
)
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.services.deps import get_storage_service


class SourcedReportComponent(Component):
    display_name = "Sourced Report"
    description = (
        "Save a report and its captured evidence. Citation checks do not assess whether sources support claims."
    )
    icon = "FileCheck2"
    name = "SourcedReport"

    inputs = [
        StrInput(name="title", display_name="Report Title", value="Research report", required=True),
        MessageInput(
            name="report",
            display_name="Report",
            info=(
                "Connect the Agent response to include its collected source evidence, "
                "or enter Markdown with [@source-id] citations."
            ),
            required=True,
        ),
        DataInput(
            name="sources",
            display_name="Additional Source Evidence",
            info="Optional Record Source outputs. Sources collected by the connected Agent are included automatically.",
            is_list=True,
            required=False,
        ),
        BoolInput(
            name="require_resolved",
            display_name="Require Available Citations",
            info="Stop before saving if citations are absent, missing, or unavailable. Disable to save a review draft.",
            value=True,
            advanced=True,
        ),
    ]
    outputs = [Output(name="artifact", display_name="Report Artifact", method="build_report")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_output = True

    async def build_report(self) -> Data:
        if self.graph is None or not self.graph.flow_id:
            msg = "Run Sourced Report inside a saved flow so its files belong to that flow."
            raise ValueError(msg)
        response = self.report
        if isinstance(response, str):
            response = Message(text=response)
        elif isinstance(response, dict):
            response = Message(**response)
        if response.error or response.properties.state != "complete" or response.text_stream is not None:
            msg = "Sourced Report needs a completed response before saving its evidence."
            raise ValueError(msg)
        run_result = (
            AgentRunResult.model_validate(response.properties.agent_run_result)
            if response.properties.agent_run_result
            else None
        )
        collected = run_result.evidence if run_result else CollectedEvidence()
        evidence = self.sources if isinstance(self.sources, list) else [self.sources] if self.sources else []
        report = SourcedReport(
            title=self.title,
            markdown=run_result.answer if run_result else response.text,
            execution=ArtifactExecution(
                flow_id=self.graph.source_flow_id or self.graph.flow_id,
                run_id=self.graph.run_id,
                node_id=self._id,
            ),
            sources=(*collected.sources, *(SourceRecord.model_validate(item.data.get("source")) for item in evidence)),
            source_uses=collected.uses,
        )
        if self.require_resolved:
            report.require_resolved_citations()
        stored = await store_report(report, get_storage_service())
        result = Data(
            data={
                "artifact": stored.report.model_dump(mode="json"),
                "citations": [item.model_dump() for item in stored.report.citations],
                "files": [
                    f"{stored.report.execution.flow_id}/{stored.markdown_name}",
                    f"{stored.report.execution.flow_id}/{stored.record_name}",
                ],
                "text": stored.report.render_markdown(),
            }
        )
        self.status = result.data
        return result
