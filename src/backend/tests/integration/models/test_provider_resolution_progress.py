"""Bounded integration regressions for provider resolution and caller-loop progress.

Each scenario runs in a child process so a synchronous bridge regression cannot
freeze pytest's event loop or leave a credential worker alive after the test.
The database, variable query, secret decryption, session scope, Agent model
selection and OpenAI client construction are production implementations.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from contextlib import ExitStack, asynccontextmanager, contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _start_app():
    """Each child configures its own database; this test needs no parent API server."""


SCENARIOS = (
    "sync-control",
    "agent-release",
    "agent-legacy-release",
    "deadline",
    "cancellation",
    "tenant-isolation",
    "policy-denial",
    "agent-http-stream",
)
OWNER = UUID("11111111-1111-1111-1111-111111111111")
OTHER = UUID("22222222-2222-2222-2222-222222222222")
MISSING = UUID("33333333-3333-3333-3333-333333333333")
SELECTION = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]


@contextmanager
def _local_openai_endpoint():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    requests = []

    class Endpoint(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            requests.append((self.path, self.headers.get("Authorization")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "local-chat"}]}).encode())

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers.get("Authorization")))
            assert payload["model"] == "local-chat"
            assert payload["stream"] is True
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for delta, finish in [({"role": "assistant", "content": "local "}, None), ({"content": "answer"}, "stop")]:
                chunk = {
                    "id": "local-completion",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "local-chat",
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                }
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_provider_resolution_progress(scenario, tmp_path):
    result = subprocess.run(  # noqa: S603 - fixed local test script and parametrized scenarios
        [sys.executable, str(Path(__file__).resolve()), scenario, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "LANGFLOW_CONFIG_DIR": str(tmp_path), "LANGFLOW_MODELS_DEV_REFRESH": "false"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'"scenario": "{scenario}"' in result.stdout


async def _scenario(scenario: str, directory: Path) -> dict:
    from langchain_openai import ChatOpenAI
    from langflow.services.auth.service import AuthService
    from langflow.services.database.models.variable.model import Variable
    from langflow.services.deps import get_settings_service
    from langflow.services.variable.constants import CREDENTIAL_TYPE
    from langflow.services.variable.service import DatabaseVariableService
    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import aget_llm, credentials
    from lfx.components.models_and_agents.agent import AgentComponent
    from lfx.services import deps
    from lfx.services.authorization.service import AuthorizationService
    from lfx.services.model_provider_policy import ModelProviderPolicyError, ModelProviderPolicyService
    from lfx.services.variable.request_scope import activate_no_env_fallback, reset_no_env_fallback
    from sqlalchemy import event, text
    from sqlalchemy.exc import TimeoutError as PoolTimeout
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = create_async_engine(
        "sqlite+aiosqlite:///" + str(directory / "variables.db"),
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.25,
    )
    settings = get_settings_service()
    auth = AuthService(settings)
    variables = DatabaseVariableService(settings)
    policy = ModelProviderPolicyService()
    authz = AuthorizationService()
    async with engine.begin() as connection:
        # Only the real variable table is needed; FK enforcement is off in SQLite.
        await connection.run_sync(lambda sync: Variable.__table__.create(sync))
    async with AsyncSession(engine) as session:
        session.add_all(
            [
                Variable(user_id=user, name="OPENAI_API_KEY", value=auth.encrypt_api_key(key), type=CREDENTIAL_TYPE)
                for user, key in [(OWNER, "sk-owned-test"), (OTHER, "sk-other-test")]
            ]
        )
        await session.commit()

    class Database:
        @asynccontextmanager
        async def _with_session(self):
            async with AsyncSession(engine, expire_on_commit=False) as session:
                yield session

    class AgentWithoutHistory(AgentComponent):
        async def get_memory_data(self):
            return []

    held = AsyncSession(engine)
    ticks = []
    releases = []
    queries = []
    finished = asyncio.Event()
    checked_out = asyncio.Event()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def observe_query(_connection, _cursor, statement, _parameters, _context, _executemany):
        queries.append(statement)
        if "FROM variable" in statement:
            checked_out.set()

    async def heartbeat():
        while not finished.is_set():
            ticks.append(len(ticks))
            await asyncio.sleep(0.005)

    async def release():
        await asyncio.sleep(0.04)
        await held.commit()
        releases.append(True)

    async def construct(user=OWNER, api_key=None):
        return await aget_llm(SELECTION, user, api_key=api_key)

    os.environ["OPENAI_API_KEY"] = "sk-server-must-not-leak"  # pragma: allowlist secret - synthetic test value
    token = activate_no_env_fallback(disabled=True)
    tasks = []
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(deps, "get_db_service", return_value=Database()))
            stack.enter_context(patch.object(credentials, "get_variable_service", return_value=variables))
            stack.enter_context(patch.object(deps, "get_model_provider_policy_service", return_value=policy))
            stack.enter_context(patch("langflow.services.deps.get_authorization_service", return_value=authz))
            stack.enter_context(patch("langflow.services.auth.utils.get_auth_service", return_value=auth))
            stack.enter_context(patch.object(model_utils, "get_variable_service", return_value=variables))
            if scenario in {"sync-control", "agent-release", "agent-legacy-release", "deadline"}:
                await held.exec(text("SELECT 1"))
                tasks.append(asyncio.create_task(heartbeat()))
                await asyncio.sleep(0)
                initial_ticks = len(ticks)
                if scenario != "deadline":
                    tasks.append(asyncio.create_task(release()))
                if scenario == "sync-control":
                    # This is the same Future.result bridge observed in the failed
                    # cluster. Its finite pool timeout is the local safety bound.
                    with pytest.raises(PoolTimeout):
                        credentials.get_all_variables_for_provider(OWNER, "OpenAI")
                    assert len(ticks) == initial_ticks
                    assert releases == []
                    assert engine.pool.checkedout() == 1
                elif scenario in {"agent-release", "agent-legacy-release"}:
                    # Saved-flow hydration supplies the key before model construction;
                    # make the held-resource wait occur in all-provider-variable lookup.
                    legacy = scenario == "agent-legacy-release"
                    agent = AgentWithoutHistory(
                        _user_id=str(OWNER),
                        model=[] if legacy else SELECTION,
                        agent_llm="OpenAI" if legacy else None,
                        model_name="gpt-4o-mini" if legacy else None,
                        api_key="sk-owned-test",  # pragma: allowlist secret - synthetic test key
                    )
                    agent.set_attributes({"tools": [], "add_current_date_tool": False, "chat_history": []})
                    model, history, _tools = await asyncio.wait_for(agent.get_agent_requirements(), 2)
                    assert isinstance(model, ChatOpenAI)
                    assert model.openai_api_key.get_secret_value() == "sk-owned-test"
                    assert model.streaming is True
                    assert history == []
                    assert releases == [True]
                    assert len(ticks) >= initial_ticks + 3
                    assert engine.pool.checkedout() == 0
                else:
                    with pytest.raises(asyncio.TimeoutError):
                        await asyncio.wait_for(
                            construct(api_key="sk-owned-test"),  # pragma: allowlist secret - synthetic test value
                            0.05,
                        )
                    assert len(ticks) >= initial_ticks + 3
                    assert engine.pool.checkedout() == 1
                    await held.commit()
                    assert engine.pool.checkedout() == 0
            elif scenario == "cancellation":
                # Pause after the actual owner-scoped SQL/decryption, while its
                # production session_scope still owns a checked-out connection.
                original = variables.get_variable

                async def pause_after_read(**kwargs):
                    value = await original(**kwargs)
                    await asyncio.Event().wait()
                    return value

                stack.enter_context(patch.object(variables, "get_variable", side_effect=pause_after_read))
                task = asyncio.create_task(construct(api_key="sk-owned-test"))
                tasks.append(task)
                await asyncio.wait_for(checked_out.wait(), 2)
                assert engine.pool.checkedout() == 1
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 2)
                assert engine.pool.checkedout() == 0
            elif scenario == "tenant-isolation":
                first, second = await asyncio.wait_for(asyncio.gather(construct(OWNER), construct(OTHER)), 2)
                assert first.openai_api_key.get_secret_value() == "sk-owned-test"
                assert second.openai_api_key.get_secret_value() == "sk-other-test"
                with pytest.raises(ValueError, match="API key"):
                    await construct(MISSING)
                assert engine.pool.checkedout() == 0
            elif scenario == "policy-denial":
                policy.set_approved_provider_ids(["Anthropic"])
                with pytest.raises(ModelProviderPolicyError):
                    await construct()
                assert queries == []
                assert engine.pool.checkedout() == 0
            elif scenario == "agent-http-stream":
                endpoint, requests = stack.enter_context(_local_openai_endpoint())
                os.environ["LANGFLOW_SSRF_ALLOWED_HOSTS"] = "127.0.0.1"
                async with AsyncSession(engine) as session:
                    session.add(
                        Variable(
                            user_id=OWNER,
                            name="OPENAI_BASE_URL",
                            value=auth.encrypt_api_key(endpoint),
                            type=CREDENTIAL_TYPE,
                        )
                    )
                    await session.commit()
                agent = AgentWithoutHistory(_user_id=str(OWNER), model=[], agent_llm="OpenAI", model_name="local-chat")
                agent.set_attributes({"tools": [], "add_current_date_tool": False, "chat_history": []})
                await held.exec(text("SELECT 1"))
                tasks.extend([asyncio.create_task(heartbeat()), asyncio.create_task(release())])
                model, _history, _tools = await asyncio.wait_for(agent.get_agent_requirements(), 2)
                graph = await agent._acreate_agent_runnable(model)
                chunks = [
                    event["data"]["chunk"].content
                    async for event in graph.astream_events({"messages": [("user", "hello")]}, version="v2")
                    if event["event"] == "on_chat_model_stream"
                ]
                assert "".join(chunks) == "local answer"
                assert [path for path, _key in requests] == ["/v1/models", "/v1/chat/completions"]
                assert all(key == "Bearer sk-owned-test" for _path, key in requests)
                assert len(ticks) >= 3
                assert releases == [True]
                assert engine.pool.checkedout() == 0
            else:
                raise AssertionError(scenario)
        return {"scenario": scenario, "ticks": len(ticks), "releases": len(releases), "queries": len(queries)}
    finally:
        reset_no_env_fallback(token)
        finished.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await held.close()
        await engine.dispose()


if __name__ == "__main__":
    sys.stdout.write(json.dumps(asyncio.run(_scenario(sys.argv[1], Path(sys.argv[2])))) + "\n")
