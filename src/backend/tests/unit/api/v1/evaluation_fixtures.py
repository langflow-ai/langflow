"""A deterministic scorer graph component; it consumes the real recorded response."""

import json

from lfx.custom import Component
from lfx.io import DataInput, MessageTextInput, Output, StrInput
from lfx.schema.data import Data


class FixtureJudge(Component):
    name = "FixtureJudge"
    display_name = "Fixture Judge"
    inputs = [
        DataInput(name="case", required=True),
        StrInput(name="outcome", value="supported"),
        MessageTextInput(name="approval", value=""),
    ]
    outputs = [Output(name="judgment", method="judge")]

    def judge(self) -> Data:
        payload = self.case.data
        matched = payload["case"]["reference"] in json.dumps(payload["response"]["outputs"])
        result = {
            "score": 1.0 if matched else 0.0,
            "reason": "Compared the recorded response to the case reference.",
            "claim_support": "unsupported" if self.outcome == "unsupported" else "supported",
            "policy": "violation" if self.outcome == "violation" else "compliant",
        }
        if self.outcome == "malformed":
            result["score"] = "perfect"
        return Data(data=result)
