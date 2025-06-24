from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import BoolInput, FloatInput, HandleInput, MessageTextInput, Output, PromptInput
from langflow.schema.message import Message


class CleanlabRemediator(Component):
    """Remediates potentially untrustworthy LLM responses based on trust scores computed by the Cleanlab Evaluator.

    This component takes a response and its associated trust score,
    and applies remediation strategies based on configurable thresholds and settings.

    Inputs:
        - response (MessageTextInput): The original LLM-generated response to be evaluated and possibly remediated.
          The CleanlabEvaluator passes this response through.
        - score (HandleInput): The trust score output from CleanlabEvaluator (expected to be a float between 0 and 1).
        - explanation (MessageTextInput): Optional textual explanation for the trust score, to be included in the
          output.
        - threshold (Input[float]): Minimum trust score required to accept the response. If the score is lower, the
          response is remediated.
        - show_untrustworthy_response (BoolInput): If true, returns the original response with a warning; if false,
          returns fallback text.
        - untrustworthy_warning_text (PromptInput): Text warning to append to responses deemed untrustworthy (when
          showing them).
        - fallback_text (PromptInput): Replacement message returned if the response is untrustworthy and should be
          hidden.

    Outputs:
        - remediated_response (Message): Either:
            • the original response,
            • the original response with appended warning, or
            • the fallback response,
          depending on the trust score and configuration.

    This component is typically used downstream of CleanlabEvaluator or CleanlabRagValidator
    to take appropriate action on low-trust responses and inform users accordingly.
    """

    display_name = "Cleanlab Remediator"
    description = (
        "Remediates an untrustworthy response based on trust score from the Cleanlab Evaluator, "
        "score threshold, and message handling settings."
    )
    icon = "Cleanlab"
    name = "CleanlabRemediator"

    inputs = [
        MessageTextInput(
            name="response",
            display_name="Response",
            info="The response to the user's query.",
            required=True,
        ),
        HandleInput(
            name="score",
            display_name="Trust Score",
            info="The trustworthiness score output from the Cleanlab Evaluator.",
            input_types=["number"],
            required=True,
        ),
        MessageTextInput(
            name="explanation",
            display_name="Explanation",
            info="The explanation from the Cleanlab Evaluator.",
            required=False,
        ),
        FloatInput(
            name="threshold",
            display_name="Threshold",
            field_type="float",
            value=0.7,
            range_spec=RangeSpec(min=0.0, max=1.0, step=0.05),
            info="Minimum score required to show the response unmodified. Reponses with scores above this threshold "
            "are considered trustworthy. Reponses with scores below this threshold are considered untrustworthy and "
            "will be remediated based on the settings below.",
            required=True,
            show=True,
        ),
        BoolInput(
            name="show_untrustworthy_response",
            display_name="Show Untrustworthy Response",
            info="If enabled, and the trust score is below the threshold, the original response is shown with the "
            "added warning. If disabled, and the trust score is below the threshold, the fallback answer is returned.",
            value=True,
        ),
        PromptInput(
            name="untrustworthy_warning_text",
            display_name="Warning for Untrustworthy Response",
            info="Warning to append to the response if Show Untrustworthy Response is enabled and trust score is "
            "below the threshold.",
            value="WARNING: The following response is potentially untrustworthy.",
        ),
        PromptInput(
            name="fallback_text",
            display_name="Fallback Answer",
            info="Response returned if the trust score is below the threshold and 'Show Untrustworthy Response' is "
            "disabled.",
            value="Based on the available information, I cannot provide a complete answer to this question.",
        ),
    ]

    outputs = [
        Output(
            display_name="Remediated Message",
            name="remediated_response",
            method="remediate_response",
            types=["Message"],
        ),
    ]

    def remediate_response(self) -> Message:
        if self.score >= self.threshold:
            self.status = f"Score {self.score:.2f} >= threshold {self.threshold:.2f} -> accepted"
            return Message(
                text=f"{self.response}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n**Trust Score:** {self.score:.2f}"
            )

        self.status = f"Score {self.score:.2f} < threshold {self.threshold:.2f} -> flagged"

        if self.show_untrustworthy_response:
            parts = [
                self.response,
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"**{self.untrustworthy_warning_text.strip()}**",
                f"**Trust Score:** {self.score:.2f}",
            ]
            if self.explanation:
                parts.append(f"**Explanation:** {self.explanation}")
            return Message(text="\n\n".join(parts))

        return Message(text=self.fallback_text)
