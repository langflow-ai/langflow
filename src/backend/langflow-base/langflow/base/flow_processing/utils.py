from typing import List

from loguru import logger

from langflow.graph.schema import ResultData, RunOutputs
from langflow.schema import Data
from langflow.schema.message import Message


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

    # Handle results without chat messages (calling flow)
    if not messages:
        # Result with a single record
        if isinstance(result_data.artifacts, dict):
            data.append(Data(data=result_data.artifacts))
        # List of artifacts
        elif isinstance(result_data.artifacts, list):
            for artifact in result_data.artifacts:
                # If multiple records are found as artifacts, return as-is
                if isinstance(artifact, Data):
                    data.append(artifact)
                else:
                    # Warn about unknown output type
                    logger.warning(f"Unable to build record output from unknown ResultData.artifact: {str(artifact)}")
        # Chat or text output
        elif result_data.results:
            data.append(Data(data={"result": result_data.results}, text_key="result"))
            return data
        else:
            return []

    if isinstance(result_data.results, dict):
        for name, result in result_data.results.items():
            dataobj: Data | Message | None = None
            if isinstance(result, Message):
                dataobj = result
            else:
                dataobj = Data(data=result, text_key=name)

            data.append(dataobj)
    else:
        data.append(Data(data=result_data.results))
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
    results = "\n".join([value.get_text() if hasattr(value, "get_text") else str(value) for value in data])
    return result + results
