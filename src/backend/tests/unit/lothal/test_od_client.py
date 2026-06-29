"""Open Design client transport tests (Story U.4).

`ODClient` is Lothal's thin HTTP transport to the OD daemon. These pin its
contract with respx (mocking the daemon): each method maps to one OD endpoint
and returns OD's parsed JSON; the optional bearer is attached when configured;
and every failure mode — transport error, non-2xx, malformed body — surfaces as
`ODConnectionError` (never a raw httpx error leaking out).
"""

import json

import httpx
import pytest
import respx
from langflow.lothal.od_client import ODClient, ODConfigError, ODConnectionError

OD_BASE = "http://open-design:7456"


async def test_create_project_sends_id_and_unwraps_project():
    # OD requires a client-supplied `id` and wraps the result as {"project": {...}}.
    with respx.mock:
        route = respx.post(f"{OD_BASE}/api/projects").mock(
            return_value=httpx.Response(200, json={"project": {"id": "od-1", "name": "App"}})
        )
        async with ODClient(OD_BASE) as od:
            result = await od.create_project(
                "App", project_id="lothal-x", pending_prompt="brief", metadata={"source": "lothal"}
            )

    assert result["id"] == "od-1"
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"id": "lothal-x", "name": "App", "pendingPrompt": "brief", "metadata": {"source": "lothal"}}


async def test_create_project_tolerates_bare_shape():
    # A bare {...} (no "project" wrapper) is also accepted.
    with respx.mock:
        respx.post(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json={"id": "od-2"}))
        async with ODClient(OD_BASE) as od:
            result = await od.create_project("App", project_id="lothal-y")
    assert result["id"] == "od-2"


async def test_create_project_without_id_is_connection_error():
    with respx.mock:
        respx.post(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json={"project": {"name": "no id"}}))
        async with ODClient(OD_BASE) as od:
            with pytest.raises(ODConnectionError):
                await od.create_project("App", project_id="lothal-z")


async def test_start_run_sends_flat_body_with_conversation():
    with respx.mock:
        route = respx.post(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json={"runId": "run-1", "conversationId": "conv-1"})
        )
        async with ODClient(OD_BASE) as od:
            result = await od.start_run(
                project_id="od-1", message="design it", conversation_id="conv-1", agent_id="codex"
            )

    assert result["runId"] == "run-1"
    sent = json.loads(route.calls.last.request.content)
    assert sent == {
        "projectId": "od-1",
        "message": "design it",
        "conversationId": "conv-1",
        "agentId": "codex",
    }


async def test_start_run_without_runid_is_connection_error():
    with respx.mock:
        respx.post(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json={}))
        async with ODClient(OD_BASE) as od:
            with pytest.raises(ODConnectionError):
                await od.start_run(project_id="od-1", message="x")


async def test_list_files_handles_bare_list_and_wrapped():
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(
            return_value=httpx.Response(200, json=[{"name": "a.html"}])
        )
        async with ODClient(OD_BASE) as od:
            assert await od.list_files("od-1") == [{"name": "a.html"}]

    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(
            return_value=httpx.Response(200, json={"files": [{"name": "b.html"}]})
        )
        async with ODClient(OD_BASE) as od:
            assert await od.list_files("od-1") == [{"name": "b.html"}]


async def test_list_projects_handles_bare_list_and_wrapped():
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(200, json=[{"id": "od-1"}]))
        async with ODClient(OD_BASE) as od:
            assert await od.list_projects() == [{"id": "od-1"}]
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects").mock(
            return_value=httpx.Response(200, json={"projects": [{"id": "od-2"}]})
        )
        async with ODClient(OD_BASE) as od:
            assert await od.list_projects() == [{"id": "od-2"}]


async def test_list_endpoints_reject_unexpected_shape():
    """A 200 whose body is neither a list nor a {key:[...]} wrapper is a connection error."""
    for path, call in (
        ("/api/projects", lambda od: od.list_projects()),
        ("/api/projects/od-1/files", lambda od: od.list_files("od-1")),
        ("/api/runs", lambda od: od.list_runs("od-1")),
    ):
        with respx.mock:
            respx.get(f"{OD_BASE}{path}").mock(return_value=httpx.Response(200, json={"unexpected": "shape"}))
            async with ODClient(OD_BASE) as od:
                with pytest.raises(ODConnectionError):
                    await call(od)


async def test_list_runs_filters_by_project_id():
    with respx.mock:
        route = respx.get(f"{OD_BASE}/api/runs").mock(
            return_value=httpx.Response(200, json=[{"id": "run-1", "status": "succeeded"}])
        )
        async with ODClient(OD_BASE) as od:
            runs = await od.list_runs("od-1")

    assert runs[0]["status"] == "succeeded"
    assert route.calls.last.request.url.params["projectId"] == "od-1"


async def test_get_file_content_returns_raw_text():
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/raw/home.html").mock(
            return_value=httpx.Response(200, text="<html>hi</html>")
        )
        async with ODClient(OD_BASE) as od:
            assert await od.get_file_content("od-1", "home.html") == "<html>hi</html>"


async def test_update_app_config_uses_put():
    # OD's app-config write is PUT (read-merge), not PATCH — verified live.
    with respx.mock:
        route = respx.put(f"{OD_BASE}/api/app-config").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        async with ODClient(OD_BASE) as od:
            await od.update_app_config({"agentCliEnv": {"codex": {"OPENAI_BASE_URL": "x"}}})

    assert route.called


async def test_bearer_attached_when_token_set():
    with respx.mock:
        route = respx.get(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json=[]))
        async with ODClient(OD_BASE, token="secret-od") as od:  # noqa: S106 - test token, not a secret
            await od.list_runs("od-1")
    assert route.calls.last.request.headers["authorization"] == "Bearer secret-od"


async def test_origin_header_is_base_origin():
    # OD's origin-guard 403s /api writes whose Host is a non-loopback DNS name unless
    # the request Origin matches OD_ALLOWED_ORIGINS. The client sends its own base
    # origin so that allow-list escape hatch can accept backend config writes (U.9).
    with respx.mock:
        route = respx.put(f"{OD_BASE}/api/app-config").mock(return_value=httpx.Response(200, json={}))
        async with ODClient(OD_BASE) as od:
            await od.update_app_config({"onboardingCompleted": True})
    assert route.calls.last.request.headers["origin"] == OD_BASE


async def test_no_bearer_when_token_absent():
    with respx.mock:
        route = respx.get(f"{OD_BASE}/api/runs").mock(return_value=httpx.Response(200, json=[]))
        async with ODClient(OD_BASE) as od:
            await od.list_runs("od-1")
    assert "authorization" not in route.calls.last.request.headers


async def test_non_2xx_is_connection_error():
    with respx.mock:
        respx.post(f"{OD_BASE}/api/projects").mock(return_value=httpx.Response(500, json={"error": "boom"}))
        async with ODClient(OD_BASE) as od:
            with pytest.raises(ODConnectionError):
                await od.create_project("App", project_id="lothal-z")


async def test_transport_failure_is_connection_error():
    with respx.mock:
        respx.get(f"{OD_BASE}/api/runs").mock(side_effect=httpx.ConnectError("unreachable"))
        async with ODClient(OD_BASE) as od:
            with pytest.raises(ODConnectionError):
                await od.list_runs("od-1")


async def test_malformed_json_is_connection_error():
    with respx.mock:
        respx.get(f"{OD_BASE}/api/projects/od-1/files").mock(
            return_value=httpx.Response(200, text="not json", headers={"content-type": "application/json"})
        )
        async with ODClient(OD_BASE) as od:
            with pytest.raises(ODConnectionError):
                await od.list_files("od-1")


def test_from_env_defaults_to_compose_host(monkeypatch):
    monkeypatch.delenv("LOTHAL_OD_BASE_URL", raising=False)
    od = ODClient.from_env()
    assert od.base_url == OD_BASE


def test_from_env_reads_base_and_token(monkeypatch):
    monkeypatch.setenv("LOTHAL_OD_BASE_URL", "http://od.test:9000/")
    monkeypatch.setenv("LOTHAL_OD_API_TOKEN", "tok")
    od = ODClient.from_env()
    assert od.base_url == "http://od.test:9000"  # trailing slash stripped


def test_from_env_blank_base_is_config_error(monkeypatch):
    monkeypatch.setenv("LOTHAL_OD_BASE_URL", "   ")
    with pytest.raises(ODConfigError):
        ODClient.from_env()
