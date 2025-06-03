import json
import os
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import UUID

from aiofile import async_open
from dotenv import dotenv_values
from loguru import logger
from sqlalchemy import text

from langflow.api.utils import cascade_delete_flow
from langflow.graph import Graph
from langflow.load.utils import replace_tweaks_with_env
from langflow.logging.logger import configure
from langflow.processing.process import process_tweaks, run_graph
from langflow.services.cache.service import AsyncBaseCacheService
from langflow.services.database.models.flow import Flow
from langflow.services.database.utils import initialize_database
from langflow.services.deps import get_cache_service, session_scope
from langflow.utils.util import update_settings


class LangflowRunnerExperimental:
    """LangflowRunnerExperimental orchestrates flow execution without a dedicated server.

    .. warning::
        This class is currently **experimental** and in a **beta phase**.
        Its API and behavior may change in future releases. Use with caution in production environments.

    Usage:
    ------
    Instantiate the class and call the `run` method with the desired flow and input.

    Example:
        runner = LangflowRunnerExperimental()
        result = await runner.run(flow="path/to/flow.json", input_value="Hello", session_id=str(uuid.uuid4()))

    """

    def __init__(
        self,
        *,
        should_initialize_db: bool = True,
        log_level: str | None = None,
        log_file: str | None = None,
        disable_logs: bool = False,
        async_log_file: bool = True,
    ):
        """Initializes the LangflowRunnerExperimental instance with optional database and logging configuration.

        Args:
            should_initialize_db: If True, initializes the database if it does not exist.
            log_level: Logging level to use (e.g., "INFO", "DEBUG").
            log_file: Path to the log file for output, if specified.
            disable_logs: If True, disables all logging output.
            async_log_file: If True, enables asynchronous logging to file.
        """
        self.should_initialize_db = should_initialize_db
        log_file_path = Path(log_file) if log_file else None
        configure(log_level=log_level, log_file=log_file_path, disable=disable_logs, async_file=async_log_file)

    async def run(
        self,
        session_id: str,  # UUID required currently
        flow: Path | str | dict,
        input_value: str,
        *,
        input_type: str = "chat",
        output_type: str = "chat",
        cache: str | None = None,
        env_file: str | None = None,
        tweaks: dict | None = None,
        stream: bool = False,
    ):
        """Executes a flow asynchronously for a given session, supporting environment variable injection, tweaks, caching, and streaming output.

        Initializes the database if needed, loads and modifies the flow schema, applies tweaks and environment variables, manages flow state in the cache and database, creates and runs the flow graph, and returns the execution result. Cleans up flow state after execution. Supports streaming output if requested.

        Args:
            session_id: Unique identifier for the session and flow execution.
            flow: The flow definition as a file path, string, or dictionary.
            input_value: The input to provide to the flow.
            input_type: The type of input, e.g., "chat".
            output_type: The type of output, e.g., "chat".
            cache: Optional cache identifier to use for this run.
            env_file: Optional path to a dotenv file for environment variable injection.
            tweaks: Optional dictionary of tweaks to apply to the flow, with support for environment variable substitution.
            stream: If True, enables streaming output.

        Returns:
            The result of the flow execution, or a streaming response if streaming is enabled.
        """
        logger.info(f"Start Handling {session_id=}")
        await self.init_db_if_needed()
        # Update settings with cache and components path
        await update_settings(cache=cache)
        flow_dict = await self.get_flow_dict(flow)
        self.set_flow_id(session_id, flow_dict)
        if env_file and tweaks is not None:
            async with async_open(Path(env_file), encoding="utf-8") as f:
                content = await f.read()
                env_vars = dotenv_values(stream=StringIO(content))
            tweaks = replace_tweaks_with_env(tweaks=tweaks, env_vars=env_vars)
        # we must modify the flow schema to set the session_id and for load_from_db=True we load the value from env vars
        self.modification(flow_dict, lambda obj, parent, key: self.modify_flow_schema(session_id, obj, parent, key))
        if tweaks is not None:
            flow_dict = process_tweaks(flow_dict, tweaks)
        await self.clear_flow_state(session_id, flow_dict)
        await self.add_flow_to_db(session_id, flow_dict)
        graph = await self.create_graph_from_flow(session_id, flow_dict)
        try:
            result = await self.run_graph(input_value, input_type, output_type, session_id, graph, stream=stream)
        finally:
            await self.clear_flow_state(session_id, flow_dict)
        logger.info(f"Finish Handling {session_id=}")
        return result

    @staticmethod
    def set_flow_id(session_id: str, flow_dict: dict) -> None:
        flow_dict["id"] = session_id

    @staticmethod
    async def add_flow_to_db(session_id: str, flow_dict: dict):
        async with session_scope() as session:
            flow_db = Flow(name=session_id, id=UUID(flow_dict["id"]), data=flow_dict.get("data", {}))
            session.add(flow_db)
            await session.commit()

    @staticmethod
    async def run_graph(
        input_value: str, input_type: str, output_type: str, session_id: str, graph: Graph, *, stream: bool
    ):
        return await run_graph(
            graph=graph,
            session_id=session_id,
            input_value=input_value,
            fallback_to_env_vars=True,
            input_type=input_type,
            output_type=output_type,
            stream=stream,
        )

    @staticmethod
    async def create_graph_from_flow(session_id: str, flow_dict: dict):
        """Creates and initializes a Graph instance from a flow dictionary for a given session.

        Args:
            session_id: The unique identifier for the session.
            flow_dict: The dictionary representing the flow configuration.

        Returns:
            An initialized Graph object ready for execution.
        """
        graph = Graph.from_payload(flow_dict, flow_id=flow_dict["id"], flow_name=flow_dict.get("name"))
        graph.session_id = session_id
        graph.set_run_id(session_id)
        await graph.initialize_run()
        return graph

    @staticmethod
    async def clear_flow_state(_session_id: str, flow_dict: dict):
        cache_service = get_cache_service()
        if isinstance(cache_service, AsyncBaseCacheService):
            await cache_service.clear()
        else:
            cache_service.clear()
        async with session_scope() as session:
            flow_id = flow_dict["id"]
            uuid_obj = flow_id if isinstance(flow_id, UUID) else UUID(str(flow_id))
            await cascade_delete_flow(session, uuid_obj)

    async def init_db_if_needed(self):
        if not await self.database_exists_check() and self.should_initialize_db:
            logger.info("Initializing database...")
            await initialize_database(fix_migration=True)
            self.should_initialize_db = False
            logger.info("Database initialized.")

    @staticmethod
    async def database_exists_check():
        async with session_scope() as session:
            try:
                result = await session.exec(text("SELECT version_num FROM public.alembic_version"))
                return result.first() is not None
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Database check failed: {e}")
                return False

    @staticmethod
    async def get_flow_dict(flow: Path | str | dict) -> dict:
        if isinstance(flow, str | Path):
            async with async_open(Path(flow), encoding="utf-8") as f:
                content = await f.read()
                return json.loads(content)
        # If input is a dictionary, assume it's a JSON object
        elif isinstance(flow, dict):
            return flow
        error_msg = "Input must be a file path (str or Path object) or a JSON object (dict)."
        raise TypeError(error_msg)

    @staticmethod
    def modify_flow_schema(session_id: str, obj: Any, parent: Any | None, _key: str | None):
        if not isinstance(obj, dict):
            return
        parent_dict = parent if isinstance(parent, dict) else {}
        parent_display = parent_dict.get("display_name", parent_dict.get("name", parent_dict.get("id", "unknown")))
        if "session_id" in obj:
            obj["session_id"] = session_id
            logger.info(f"Setting {session_id=} for {parent_display=}")
        if obj.get("load_from_db"):
            obj["load_from_db"] = False
            env_var_name = obj["value"]
            if not env_var_name:
                return
            env_var_value = os.getenv(env_var_name)
            if not env_var_value:
                error_msg = f"Environment variable {env_var_name} not set for {parent_display}"
                raise ValueError(error_msg)
            obj["value"] = os.getenv(env_var_name)
            logger.info(f"Loading env var {env_var_name=} for {parent_display=}")

    def modification(self, obj: Any, func: Callable[[Any, Any | None, str | None], None], parent: Any = None) -> None:
        """Recursively apply a function to all elements in a nested structure (dict or list).

        The function is called with three arguments: the current object, its parent, and the key (if applicable).
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                func(value, parent, key)
                self.modification(value, func, obj)
            return
        if isinstance(obj, list):
            for item in obj:
                func(item, parent, None)
                self.modification(item, func, obj)
            return
        # primitive types (int, float, str, bool, None)
        func(obj, parent, None)
