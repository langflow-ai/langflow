import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from aiofile import async_open
from loguru import logger
from sqlmodel import delete, select, text

from langflow.api.utils import cascade_delete_flow
from langflow.graph import Graph
from langflow.graph.vertex.param_handler import ParameterHandler
from langflow.load.utils import replace_tweaks_with_env
from langflow.logging.logger import configure
from langflow.processing.process import process_tweaks, run_graph
from langflow.services.auth.utils import (
    get_password_hash,
)
from langflow.services.cache.service import AsyncBaseCacheService
from langflow.services.database.models import Flow, User, Variable
from langflow.services.database.utils import initialize_database
from langflow.services.deps import get_cache_service, get_storage_service, session_scope
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
        log_rotation: str | None = None,
        disable_logs: bool = False,
        async_log_file: bool = True,
    ):
        self.should_initialize_db = should_initialize_db
        log_file_path = Path(log_file) if log_file else None
        configure(
            log_level=log_level,
            log_file=log_file_path,
            log_rotation=log_rotation,
            disable=disable_logs,
            async_file=async_log_file,
        )

    async def run(
        self,
        session_id: str,  # UUID required currently
        flow: Path | str | dict,
        input_value: str,
        *,
        input_type: str = "chat",
        output_type: str = "all",
        cache: str | None = None,
        stream: bool = False,
        user_id: str | None = None,
        generate_user: bool = False,  # If True, generates a new user for the flow
        cleanup: bool = True,  # If True, clears flow state after execution
        tweaks_values: dict | None = None,
    ):
        try:
            logger.info(f"Start Handling {session_id=}")
            await self.init_db_if_needed()
            # Update settings with cache and components path
            await update_settings(cache=cache)
            if generate_user:
                user = await self.generate_user()
                user_id = str(user.id)
            flow_dict = await self.prepare_flow_and_add_to_db(
                flow=flow,
                user_id=user_id,
                session_id=session_id,
                tweaks_values=tweaks_values,
            )
            return await self.run_flow(
                input_value=input_value,
                session_id=session_id,
                flow_dict=flow_dict,
                input_type=input_type,
                output_type=output_type,
                user_id=user_id,
                stream=stream,
            )
        finally:
            if cleanup and user_id:
                await self.clear_user_state(user_id=user_id)

    async def run_flow(
        self,
        *,
        input_value: str,
        session_id: str,
        flow_dict: dict,
        input_type: str = "chat",
        output_type: str = "all",
        user_id: str | None = None,
        stream: bool = False,
    ):
        graph = await self.create_graph_from_flow(session_id, flow_dict, user_id=user_id)
        try:
            result = await self.run_graph(input_value, input_type, output_type, session_id, graph, stream=stream)
        finally:
            await self.clear_flow_state(flow_dict)
        logger.info(f"Finish Handling {session_id=}")
        return result

    async def prepare_flow_and_add_to_db(
        self,
        *,
        flow: Path | str | dict,
        user_id: str | None = None,
        custom_flow_id: str | None = None,
        session_id: str | None = None,
        tweaks_values: dict | None = None,
    ) -> dict:
        flow_dict = await self.get_flow_dict(flow)
        session_id = session_id or custom_flow_id or str(uuid4())
        if custom_flow_id:
            flow_dict["id"] = custom_flow_id
        flow_dict = self.process_tweaks(flow_dict, tweaks_values=tweaks_values)
        await self.clear_flow_state(flow_dict)
        await self.add_flow_to_db(flow_dict, user_id=user_id)
        return flow_dict

    def process_tweaks(self, flow_dict: dict, tweaks_values: dict | None = None) -> dict:
        tweaks: dict | None = None
        tweaks_values = tweaks_values or os.environ.copy()
        for vertex in Graph.from_payload(flow_dict).vertices:
            param_handler = ParameterHandler(vertex, get_storage_service())
            field_params, load_from_db_fields = param_handler.process_field_parameters()
            for db_field in load_from_db_fields:
                if field_params[db_field]:
                    tweaks = tweaks or {}
                    tweaks[vertex.id] = tweaks.get(vertex.id, {})
                    tweaks[vertex.id][db_field] = field_params[db_field]
        if tweaks is not None:
            tweaks = replace_tweaks_with_env(tweaks=tweaks, env_vars=tweaks_values)
            flow_dict = process_tweaks(flow_dict, tweaks)

        # Recursively update load_from_db fields
        def update_load_from_db(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == "load_from_db" and value is True:
                        obj[key] = False
                    else:
                        update_load_from_db(value)
            elif isinstance(obj, list):
                for item in obj:
                    update_load_from_db(item)

        update_load_from_db(flow_dict)
        return flow_dict

    async def generate_user(self) -> User:
        async with session_scope() as session:
            user_id = str(uuid4())
            user = User(id=user_id, username=user_id, password=get_password_hash(str(uuid4())), is_active=True)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    @staticmethod
    async def add_flow_to_db(flow_dict: dict, user_id: str | None):
        async with session_scope() as session:
            flow_db = Flow(
                name=flow_dict.get("name"), id=UUID(flow_dict["id"]), data=flow_dict.get("data", {}), user_id=user_id
            )
            session.add(flow_db)
            await session.commit()

    @staticmethod
    async def run_graph(
        input_value: str,
        input_type: str,
        output_type: str,
        session_id: str,
        graph: Graph,
        *,
        stream: bool,
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
    async def create_graph_from_flow(session_id: str, flow_dict: dict, user_id: str | None = None):
        graph = Graph.from_payload(
            payload=flow_dict, flow_id=flow_dict["id"], flow_name=flow_dict.get("name"), user_id=user_id
        )
        graph.session_id = session_id
        graph.set_run_id(session_id)
        graph.user_id = user_id
        await graph.initialize_run()
        return graph

    @staticmethod
    async def clear_flow_state(flow_dict: dict):
        cache_service = get_cache_service()
        if isinstance(cache_service, AsyncBaseCacheService):
            await cache_service.clear()
        else:
            cache_service.clear()
        async with session_scope() as session:
            flow_id = flow_dict["id"]
            uuid_obj = flow_id if isinstance(flow_id, UUID) else UUID(str(flow_id))
            await cascade_delete_flow(session, uuid_obj)

    @staticmethod
    async def clear_user_state(user_id: str):
        async with session_scope() as session:
            flows = await session.exec(select(Flow.id).where(Flow.user_id == user_id))
            flow_ids: list[UUID] = [fid for fid in flows.scalars().all() if fid is not None]
            for flow_id in flow_ids:
                await cascade_delete_flow(session, flow_id)
            await session.exec(delete(Variable).where(Variable.user_id == user_id))
            await session.exec(delete(User).where(User.id == user_id))

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
