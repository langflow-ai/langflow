from lfx.custom import Component
from lfx.io import BoolInput, DataInput, MessageTextInput, Output, StrInput
from lfx.projects.artifacts import ArtifactExecution, SourcedReport, SourceRecord, store_report
from lfx.schema.data import Data
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
        MessageTextInput(
            name="report",
            display_name="Report",
            info="Generated Markdown using the [@source-id] citations returned by Record Source.",
            required=True,
        ),
        DataInput(
            name="sources",
            display_name="Source Evidence",
            info="Original Record Source outputs, kept separately from generated report text.",
            is_list=True,
            required=True,
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
        evidence = self.sources if isinstance(self.sources, list) else [self.sources]
        report = SourcedReport(
            title=self.title,
            markdown=self.report,
            execution=ArtifactExecution(
                flow_id=self.graph.source_flow_id or self.graph.flow_id,
                run_id=self.graph.run_id,
                node_id=self._id,
            ),
            sources=tuple(SourceRecord.model_validate(item.data.get("source")) for item in evidence),
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
