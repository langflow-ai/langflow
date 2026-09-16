import json

from lfx.custom import Component
from lfx.io import MultilineInput, Output
from lfx.schema.data import Data


class EvaluationInputComponent(Component):
    display_name = "Evaluation Input"
    description = "The case, reference, candidate response, and recorded evidence supplied to a scorer."
    icon = "ClipboardList"
    name = "EvaluationInput"
    inputs = [
        MultilineInput(
            name="preview",
            display_name="Preview case (JSON)",
            value='{"case":{"input":"Question","reference":"Expected answer"},"response":{"outputs":{}}}',
            info="Used only for canvas previews. Suite runs supply the actual case and response.",
        )
    ]
    outputs = [Output(name="case", display_name="Case", method="build_case")]

    def build_case(self) -> Data:
        from lfx.projects.evaluations import EVAL_INPUT_VARIABLE

        variables = (self.graph.context or {}).get("request_variables", {}) if self.graph else {}
        raw = variables.get(EVAL_INPUT_VARIABLE, self.preview)
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get("case"), dict) or "response" not in value:
            msg = "Evaluation Input needs a case and its actual workflow response."
            raise ValueError(msg)
        return Data(data=value)
