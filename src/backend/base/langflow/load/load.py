import json
from io import StringIO
from pathlib import Path

from aiofile import async_open
from dotenv import dotenv_values
from loguru import logger

from langflow.graph.graph.base import Graph
from langflow.graph.schema import RunOutputs
from langflow.load.utils import replace_tweaks_with_env
from langflow.logging.logger import configure
from langflow.processing.process import process_tweaks, run_graph
from langflow.utils.async_helpers import run_until_complete
from langflow.utils.util import update_settings


async def aload_flow_from_json(
    flow: Path | str | dict,
    *,
    tweaks: dict | None = None,
    log_level: str | None = None,
    log_file: str | None = None,
    env_file: str | None = None,
    cache: str | None = None,
    disable_logs: bool | None = True,
) -> Graph:
    """Load a flow graph from a JSON file or a JSON object.

    Args:
        flow (Union[Path, str, dict]): The flow to load. It can be a file path (str or Path object)
            or a JSON object (dict).
        tweaks (Optional[dict]): Optional tweaks to apply to the loaded flow graph.
        log_level (Optional[str]): Optional log level to configure for the flow processing.
        log_file (Optional[str]): Optional log file to configure for the flow processing.
        env_file (Optional[str]): Optional .env file to override environment variables.
        cache (Optional[str]): Optional cache path to update the flow settings.
        disable_logs (Optional[bool], default=True): Optional flag to disable logs during flow processing.
            If log_level or log_file are set, disable_logs is not used.

    Returns:
        Graph: The loaded flow graph as a Graph object.

    Raises:
        TypeError: If the input is neither a file path (str or Path object) nor a JSON object (dict).

    """
    # If input is a file path, load JSON from the file
    log_file_path = Path(log_file) if log_file else None
    configure(log_level=log_level, log_file=log_file_path, disable=disable_logs, async_file=True)

    # override env variables with .env file
    if env_file and tweaks is not None:
        async with async_open(Path(env_file), encoding="utf-8") as f:
            content = await f.read()
            env_vars = dotenv_values(stream=StringIO(content))
        tweaks = replace_tweaks_with_env(tweaks=tweaks, env_vars=env_vars)

    # Update settings with cache and components path
    await update_settings(cache=cache)

    if isinstance(flow, str | Path):
        async with async_open(Path(flow), encoding="utf-8") as f:
            content = await f.read()
            flow_graph = json.loads(content)
    # If input is a dictionary, assume it's a JSON object
    elif isinstance(flow, dict):
        flow_graph = flow
    else:
        msg = "Input must be either a file path (str) or a JSON object (dict)"
        raise TypeError(msg)

    graph_data = flow_graph["data"]
    if tweaks is not None:
        graph_data = process_tweaks(graph_data, tweaks)

    return Graph.from_payload(graph_data)


def load_flow_from_json(
    flow: Path | str | dict,
    *,
    tweaks: dict | None = None,
    log_level: str | None = None,
    log_file: str | None = None,
    env_file: str | None = None,
    cache: str | None = None,
    disable_logs: bool | None = True,
) -> Graph:
    """Load a flow graph from a JSON file or a JSON object.

    Args:
        flow (Union[Path, str, dict]): The flow to load. It can be a file path (str or Path object)
            or a JSON object (dict).
        tweaks (Optional[dict]): Optional tweaks to apply to the loaded flow graph.
        log_level (Optional[str]): Optional log level to configure for the flow processing.
        log_file (Optional[str]): Optional log file to configure for the flow processing.
        env_file (Optional[str]): Optional .env file to override environment variables.
        cache (Optional[str]): Optional cache path to update the flow settings.
        disable_logs (Optional[bool], default=True): Optional flag to disable logs during flow processing.
            If log_level or log_file are set, disable_logs is not used.

    Returns:
        Graph: The loaded flow graph as a Graph object.

    Raises:
        TypeError: If the input is neither a file path (str or Path object) nor a JSON object (dict).

    """
    return run_until_complete(
        aload_flow_from_json(
            flow,
            tweaks=tweaks,
            log_level=log_level,
            log_file=log_file,
            env_file=env_file,
            cache=cache,
            disable_logs=disable_logs,
        )
    )


async def arun_flow_from_json(
    flow: Path | str | dict,
    input_value: str,
    *,
    session_id: str | None = None,
    tweaks: dict | None = None,
    input_type: str = "chat",
    output_type: str = "chat",
    output_component: str | None = None,
    log_level: str | None = None,
    log_file: str | None = None,
    env_file: str | None = None,
    cache: str | None = None,
    disable_logs: bool | None = True,
    fallback_to_env_vars: bool = False,
    stream: bool = False,  # <- new argument

) -> list[RunOutputs]:
    
    """Run a flow from a JSON file or dictionary.

    Args:
        flow (Union[Path, str, dict]): The path to the JSON file or the JSON dictionary representing the flow.
        input_value (str): The input value to be processed by the flow.
        session_id (str | None, optional): The session ID to be used for the flow. Defaults to None.
        tweaks (Optional[dict], optional): Optional tweaks to be applied to the flow. Defaults to None.
        input_type (str, optional): The type of the input value. Defaults to "chat".
        output_type (str, optional): The type of the output value. Defaults to "chat".
        output_component (Optional[str], optional): The specific component to output. Defaults to None.
        log_level (Optional[str], optional): The log level to use. Defaults to None.
        log_file (Optional[str], optional): The log file to write logs to. Defaults to None.
        env_file (Optional[str], optional): The environment file to load. Defaults to None.
        cache (Optional[str], optional): The cache directory to use. Defaults to None.
        disable_logs (Optional[bool], optional): Whether to disable logs. Defaults to True.
        fallback_to_env_vars (bool, optional): Whether Global Variables should fallback to environment variables if
            not found. Defaults to False.

    Returns:
        List[RunOutputs]: A list of RunOutputs objects representing the results of running the flow.
    """
    if tweaks is None:
        tweaks = {}
    tweaks["stream"] = stream #False
    graph = await aload_flow_from_json(
        flow=flow,
        tweaks=tweaks,
        log_level=log_level,
        log_file=log_file,
        env_file=env_file,
        cache=cache,
        disable_logs=disable_logs,
    )
    result = await run_graph(
        graph=graph,
        session_id=session_id,
        input_value=input_value,
        input_type=input_type,
        output_type=output_type,
        output_component=output_component,
        fallback_to_env_vars=fallback_to_env_vars,
    )
    await logger.complete()
    return result


def run_flow_from_json(
    flow: Path | str | dict,
    input_value: str,
    *,
    session_id: str | None = None,
    tweaks: dict | None = None,
    input_type: str = "chat",
    output_type: str = "chat",
    output_component: str | None = None,
    log_level: str | None = None,
    log_file: str | None = None,
    env_file: str | None = None,
    cache: str | None = None,
    disable_logs: bool | None = True,
    fallback_to_env_vars: bool = False,
) -> list[RunOutputs]:
    """Run a flow from a JSON file or dictionary.

    Note:
        This function is a synchronous wrapper around `arun_flow_from_json`.
        It creates an event loop if one does not exist and runs the flow.

    Args:
        flow (Union[Path, str, dict]): The path to the JSON file or the JSON dictionary representing the flow.
        input_value (str): The input value to be processed by the flow.
        session_id (str | None, optional): The session ID to be used for the flow. Defaults to None.
        tweaks (Optional[dict], optional): Optional tweaks to be applied to the flow. Defaults to None.
        input_type (str, optional): The type of the input value. Defaults to "chat".
        output_type (str, optional): The type of the output value. Defaults to "chat".
        output_component (Optional[str], optional): The specific component to output. Defaults to None.
        log_level (Optional[str], optional): The log level to use. Defaults to None.
        log_file (Optional[str], optional): The log file to write logs to. Defaults to None.
        env_file (Optional[str], optional): The environment file to load. Defaults to None.
        cache (Optional[str], optional): The cache directory to use. Defaults to None.
        disable_logs (Optional[bool], optional): Whether to disable logs. Defaults to True.
        fallback_to_env_vars (bool, optional): Whether Global Variables should fallback to environment variables if
            not found. Defaults to False.

    Returns:
        List[RunOutputs]: A list of RunOutputs objects representing the results of running the flow.
    """
    return run_until_complete(
        arun_flow_from_json(
            flow,
            input_value,
            session_id=session_id,
            tweaks=tweaks,
            input_type=input_type,
            output_type=output_type,
            output_component=output_component,
            log_level=log_level,
            log_file=log_file,
            env_file=env_file,
            cache=cache,
            disable_logs=disable_logs,
            fallback_to_env_vars=fallback_to_env_vars,
        )
    )
