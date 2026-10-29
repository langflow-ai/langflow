import json

from lfx.inputs.inputs import DictInput
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent, FastAFError
from lfx_fastaf._inputs import (
    api_key_input,
    scrape_inputs,
    text_input,
)


class FastAFExtractComponent(FastAFBaseComponent):
    display_name = "FastAF Extract Page Data"
    description = "Extract data using AI instructions on /v1/scrape. Adds 10 credits to the scrape base cost."
    name = "FastAFExtract"
    endpoint = "scrape"
    result_keys = ()
    inputs = [
        api_key_input(),
        *scrape_inputs(),
        text_input(
            "prompt",
            "Extraction Prompt",
            "Instructions for AI extraction. Supply a prompt, rules or both.",
            tool_mode=True,
        ),
        DictInput(
            name="rules",
            display_name="Extraction Rules",
            value={},
            info="Field-to-instruction map, e.g. title: page title. AI adds 10 credits once.",
            tool_mode=True,
        ),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fastaf_extract")]

    def request_body(self) -> dict:
        rules = self.rules
        if not isinstance(rules, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in rules.items()):
            msg = "Extraction Rules must map field names to instruction strings."
            raise FastAFError(msg)
        if not (self.prompt or "").strip() and not rules:
            msg = "Provide an extraction prompt or nonempty rules."
            raise FastAFError(msg)
        return {
            **self.scrape_body(),
            "ai_query": self.prompt,
            "ai_extract_rules": json.dumps(rules, separators=(",", ":")) if rules else None,
        }

    def fastaf_extract(self) -> DataFrame:
        return DataFrame(self.fetch_content())
