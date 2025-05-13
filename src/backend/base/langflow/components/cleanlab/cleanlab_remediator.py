from langflow.custom import Component
from langflow.io import (
    MessageTextInput,
    Output,
    BoolInput,
    HandleInput,
)
from langflow.template import Input
from langflow.schema.message import Message
from langflow.field_typing.range_spec import RangeSpec


class CleanlabRemediator(Component):
    """
    A component that remediates potentially untrustworthy LLM responses based on trust scores computed by the Cleanlab Evaluator.
    
    This component takes a response and its associated trust score,
    and applies remediation strategies based on configurable thresholds and settings.
    
    The component can:
    - Pass through trustworthy responses that meet a minimum trust score threshold
    - Add warning messages to responses that fall below the threshold
    - Replace untrustworthy responses with a fallback message
    
    Outputs:
        - Remediated Message: The original response, modified response with warnings, 
          or fallback message depending on the trust score and configuration settings

          The remediated message is determined by the following rules:
          - If the trust score is above or equal to the threshold, the original response is returned.
          - If the trust score is below the threshold:
            - If the show untrustworthy response option is enabled, the original response is returned with a warning message.
            - If the show untrustworthy response option is disabled, the fallback message is returned.
    
    This component works well in conjunction with the CleanlabEvaluator or CleanlabRAGEvaluator to create a complete trust evaluation and remediation pipeline.
    """
    display_name = "Cleanlab Remediator"
    description = "Remediates an untrustworthy response based on trust score from the Cleanlab Evaluator, score threshold, and message handling settings."
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
        Input(
            name="threshold",
            display_name="Threshold",
            field_type="float",
            value=0.7,
            range_spec=RangeSpec(min=0.0, max=1.0, step=0.05),
            info="Minimum score required to show the response unmodified. Reponses with scores above this threshold are considered trustworthy. Reponses with scores below this threshold are considered untrustworthy and will be remediated based on the settings below.",
            required=True,
            show=True,
        ),
        BoolInput(
            name="show_untrustworthy_response",
            display_name="Show Untrustworthy Response",
            info="If enabled, and the trust score is below the threshold, the original response is shown with the added warning. If disabled, and the trust score is below the threshold, the fallback answer is returned.",
            value=True,
        ),
        MessageTextInput(
            name="untrustworthy_warning_text",
            display_name="Warning for Untrustworthy Response",
            info="Warning to append to the response if Show Untrustworthy Response is enabled and trust score is below the threshold.",
            value="⚠️ WARNING: The following response is potentially untrustworthy.",
        ),
        MessageTextInput(
            name="fallback_text",
            display_name="Fallback Answer",
            info="Response returned if the trust score is below the threshold and 'Show Untrustworthy Response' is disabled.",
            value="Based on the available information, I cannot provide a complete answer to this question.",
        ),
    ]

    outputs = [
        Output(display_name="Remediated Message", name="remediated_response", method="remediate_response", types=["Message"]),
    ]

    def remediate_response(self) -> Message:
        if self.score >= self.threshold:
            self.status = f"Score {self.score:.2f} ≥ threshold {self.threshold:.2f} → accepted"
            return Message(text=f"{self.response}\n\n-----------------------------------------------\nTrust Score: {self.score:.2f}")

        self.status = f"Score {self.score:.2f} < threshold {self.threshold:.2f} → flagged"

        if self.show_untrustworthy_response:
            sections = [
                self.response,
                "\n-----------------------------------------------\n",
                self.untrustworthy_warning_text,
                f"\nTrust Score: {self.score:.2f}\n",
            ]
            if self.explanation:
                sections.append(f"Explanation: {self.explanation}")
            return Message(text="\n".join(sections))

        return Message(text=self.fallback_text)
