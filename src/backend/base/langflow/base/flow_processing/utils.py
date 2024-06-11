from typing import List

from langflow.graph.schema import ResultData, RunOutputs
from langflow.schema import Record


def build_records_from_run_outputs(run_outputs: RunOutputs) -> List[Record]:
    """
    Build a list of records from the given RunOutputs.

    Args:
        run_outputs (RunOutputs): The RunOutputs object containing the output data.

    Returns:
        List[Record]: A list of records built from the RunOutputs.

    """
    if not run_outputs:
        return []
    records = []
    for result_data in run_outputs.outputs:
        if result_data:
            records.extend(build_records_from_result_data(result_data))
    return records


def build_records_from_result_data(result_data: ResultData, get_final_results_only: bool = True) -> List[Record]:
    """
    Build a list of records from the given ResultData.

    Args:
        result_data (ResultData): The ResultData object containing the result data.
        get_final_results_only (bool, optional): Whether to include only final results. Defaults to True.

    Returns:
        List[Record]: A list of records built from the ResultData.

    """
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


def format_flow_output_records(records: List[Record]) -> str:
    """
    Format the flow output records into a string.

    Args:
        records (List[Record]): The list of records to format.

    Returns:
        str: The formatted flow output records.

    """
    result = "Flow run output:\n"
    results = "\n".join([record.result for record in records if record.data["message"]])
    return result + results
