from typing import List

from langflow.graph.schema import ResultData, RunOutputs
from langflow.schema.schema import Record


def build_records_from_run_outputs(run_outputs: RunOutputs) -> List[Record]:
    if not run_outputs:
        return []
    records = []
    for result_data in run_outputs.outputs:
        records.extend(build_records_from_result_data(result_data))
    return records


def build_records_from_result_data(result_data: ResultData, get_final_results_only: bool = True) -> List[Record]:
    messages = result_data.messages
    if not messages:
        return []
    records = []
    for message in messages:
        message_dict = message if isinstance(message, dict) else message.model_dump()
        if get_final_results_only:
            result_data_dict = result_data.model_dump()
            results = result_data_dict.get("results", {})
            inner_result = results.get("result", {})
        record = Record(data={"result": inner_result, "message": message_dict}, text_key="result")
        records.append(record)
    return records
