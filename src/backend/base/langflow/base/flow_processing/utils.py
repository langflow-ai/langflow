from typing import List

from langflow.graph.schema import ResultData, RunOutputs
from langflow.schema import Data


def build_data_from_run_outputs(run_outputs: RunOutputs) -> List[Data]:
    """
    Build a list of data from the given RunOutputs.

    Args:
        run_outputs (RunOutputs): The RunOutputs object containing the output data.

    Returns:
        List[Data]: A list of data built from the RunOutputs.

    """
    if not run_outputs:
        return []
    data = []
    for result_data in run_outputs.outputs:
        if result_data:
            data.extend(build_data_from_result_data(result_data))
    return data


def build_data_from_result_data(result_data: ResultData, get_final_results_only: bool = True) -> List[Data]:
    """
    Build a list of data from the given ResultData.

    Args:
        result_data (ResultData): The ResultData object containing the result data.
        get_final_results_only (bool, optional): Whether to include only final results. Defaults to True.

    Returns:
        List[Data]: A list of data built from the ResultData.

    """
    messages = result_data.messages
    if not messages:
        return []
    data = []
    for message in messages:
        message_dict = message if isinstance(message, dict) else message.model_dump()
        if get_final_results_only:
            result_data_dict = result_data.model_dump()
            results = result_data_dict.get("results", {})
            inner_result = results.get("result", {})
        record = Data(data={"result": inner_result, "message": message_dict}, text_key="result")
        data.append(record)
    return data


def format_flow_output_data(data: List[Data]) -> str:
    """
    Format the flow output data into a string.

    Args:
        data (List[Data]): The list of data to format.

    Returns:
        str: The formatted flow output data.

    """
    result = "Flow run output:\n"
    results = "\n".join([value.result for value in data if value.data["message"]])
    return result + results
