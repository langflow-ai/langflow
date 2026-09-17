from lfx.custom import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data


class EvaluationResultComponent(Component):
    display_name = "Evaluation Result"
    description = "Validate a scorer's score, reason, claim support, and policy outcome. Missing judgments cannot pass."
    icon = "ClipboardCheck"
    name = "EvaluationResult"
    inputs = [
        DataInput(name="case", display_name="Evaluation case", required=True),
        DataInput(
            name="judgment",
            display_name="Judgment",
            required=False,
            info=(
                'Connect a Data record: {"score": 0.0, "reason": "Why", '
                '"claim_support": "supported|unsupported|not_evaluated", '
                '"policy": "compliant|violation|not_evaluated"}. '
                "Use ordinary Prompt Template, model, and structured-output components to build your scorer."
            ),
        ),
    ]
    outputs = [Output(name="evaluation", display_name="Evaluation", method="build_result")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_output = True

    def build_result(self) -> Data:
        from lfx.projects.evaluations import EvalVerdict

        if self.judgment is None:
            msg = "Connect a scorer judgment to Evaluation Result before running an evaluation."
            raise ValueError(msg)
        verdict = EvalVerdict.model_validate(self.judgment.data)
        return Data(data={"evaluation": verdict.model_dump()})
