from lfx.custom import Component
from lfx.io import BoolInput, MessageTextInput, Output, StrInput
from lfx.projects.artifacts import SOURCE_EVIDENCE_KIND, SourceRecord
from lfx.schema.data import Data


class RecordSourceComponent(Component):
    display_name = "Record Source"
    description = (
        "Keep retrieved text with a stable citation ID. Connect the original source content before summarizing."
    )
    icon = "BookOpenCheck"
    name = "RecordSource"

    inputs = [
        StrInput(name="uri", display_name="Source Location", required=True),
        StrInput(name="title", display_name="Source Title", required=True),
        MessageTextInput(name="content", display_name="Retrieved Text", value=""),
        BoolInput(name="available", display_name="Evidence Available", value=True, advanced=True),
        StrInput(name="unavailable_reason", display_name="Unavailable Reason", value="", advanced=True),
    ]
    outputs = [Output(name="source", display_name="Source Evidence", method="record_source")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_output = True

    def record_source(self) -> Data:
        source = SourceRecord(
            uri=self.uri,
            title=self.title,
            content=self.content,
            availability="available" if self.available else "unavailable",
            unavailable_reason=self.unavailable_reason,
        )
        result = Data(
            data={
                "kind": SOURCE_EVIDENCE_KIND,
                "source": source.model_dump(mode="json"),
                "text": (
                    f"Citation: [@{source.id}]\nTitle: {source.title}\nSource: {source.uri}\n\n"
                    + (source.content if self.available else f"Evidence unavailable: {source.unavailable_reason}")
                ),
            }
        )
        self.status = result.data
        return result
