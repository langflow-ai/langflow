"""Evidence-producing component for the real sourced-artifact evaluation test."""

from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.projects.artifacts import SourceRecord
from lfx.schema.data import Data
from lfx.schema.message import Message


class FixtureEvidence(Component):
    name = "FixtureEvidence"
    display_name = "Fixture Evidence"
    inputs = [MessageTextInput(name="query", required=True)]
    outputs = [
        Output(name="report", method="build_report", group_outputs=True),
        Output(name="source", method="build_source", group_outputs=True),
    ]

    def build_source(self) -> Data:
        source = SourceRecord(uri="fixture://study", title="Study", content="SOURCE RESULT")
        return Data(data={"source": source.model_dump(mode="json")})

    def build_report(self) -> Message:
        return Message(text=f"SOURCE RESULT [@{self.build_source().data['source']['id']}]")
