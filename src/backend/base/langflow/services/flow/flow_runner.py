import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

from aiofile import async_open
from loguru import logger
from sqlalchemy import text

from langflow.api.utils import cascade_delete_flow
from langflow.graph import Graph
from langflow.load import aload_flow_from_json
from langflow.processing.process import run_graph
from langflow.services.database.models.flow import Flow
from langflow.services.database.utils import initialize_database
from langflow.services.deps import get_cache_service, session_scope


class LangFlowRunner:
    should_initialize_db: bool = True

    async def run(
        self,
        flow: Path | str | dict,
        input_value: str,
        input_type: str = "chat",
        output_type: str = "chat",
        session_id: str | None = None,
    ):
        logger.info(f"Start Handling {session_id=}")
        await self.init_db_if_needed()
        flow_dict = await self.get_flow_dict(flow)
        # we must modify the flow schema to set the session_id and for load_from_db=True we load the value from env vars
        self.modification(flow_dict, lambda obj, parent, key: self.modify_flow_schema(session_id, obj, parent, key))
        await self.add_flow_to_db(session_id, flow_dict)
        await self.clear_flow_state(session_id, flow_dict)
        graph = await self.create_graph_from_flow(session_id, flow_dict)
        try:
            result = await self.run_graph(input_value, input_type, output_type, session_id, graph)
        finally:
            await self.clear_flow_state(session_id, flow_dict)
        logger.info(f"Finish Handling {session_id=}")
        return result

    @staticmethod
    async def add_flow_to_db(session_id: str, flow_dict: dict):
        async with session_scope() as session:
            flow_dict["id"] = session_id
            flow_db = Flow(name=session_id, id=UUID(flow_dict["id"]), data=flow_dict.get("data", {}))
            session.add(flow_db)
            await session.commit()

    @staticmethod
    async def run_graph(input_value: str, input_type: str, output_type: str, session_id: str, graph: Graph):
        return await run_graph(
            graph=graph,
            session_id=session_id,
            input_value=input_value,
            fallback_to_env_vars=True,
            input_type=input_type,
            output_type=output_type,
        )

    @staticmethod
    async def create_graph_from_flow(session_id: str, flow_dict: dict):
        graph = await aload_flow_from_json(flow=flow_dict, disable_logs=False)
        graph.flow_id = session_id
        return graph

    @staticmethod
    async def clear_flow_state(_session_id: str, flow_dict: dict):
        await get_cache_service().clear()
        async with session_scope() as session:
            await cascade_delete_flow(session, UUID(flow_dict["id"]))

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
