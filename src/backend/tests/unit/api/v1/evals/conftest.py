import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from langflow.api import router as api_router_module
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope
from sqlmodel import col, func, select

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
TERMINAL = {"completed", "failed", "cancelled"}


@pytest.fixture(autouse=True)
def evals_enabled(monkeypatch: pytest.MonkeyPatch):
    """The flag is read when the routes are mounted, so mount them for this test."""
    monkeypatch.setattr(api_router_module.FEATURE_FLAGS, "evals", True)
    routes = api_router_module.router_v1.routes
    mounted = len(routes)
    api_router_module.include_evals_routers(api_router_module.router_v1)
    yield
    del routes[mounted:]


def load_flow_data(filename: str) -> dict:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))["data"]


async def create_flow(client, headers, filename: str = "chat_echo_no_llm.json", name: str = "Echo") -> dict:
    response = await client.post(
        "api/v1/flows/", json={"name": name, "data": load_flow_data(filename)}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_dataset(client, headers, name: str, rows: Sequence[tuple[str, str | None]]) -> dict:
    response = await client.post("api/v1/datasets/", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    dataset = response.json()
    for start in range(0, len(rows), 500):
        chunk = [{"input": q, "expected_output": a} for q, a in rows[start : start + 500]]
        added = await client.post(f"api/v1/datasets/{dataset['id']}/items", json={"items": chunk}, headers=headers)
        assert added.status_code == 201, added.text
    return dataset


async def create_evaluation(client, headers, flow_id: str, dataset_id: str, scorers=None, **extra) -> dict:
    payload = {
        "flow_id": flow_id,
        "dataset_id": dataset_id,
        "scorers": scorers or [{"type": "exact_match", "name": "exact"}],
        **extra,
    }
    response = await client.post("api/v1/evaluations", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def start_run(client, headers, evaluation_id: str, version_id: str | None = None) -> dict:
    body = {"flow_version_id": version_id} if version_id else {}
    response = await client.post(f"api/v1/evaluations/{evaluation_id}/runs", json=body, headers=headers)
    assert response.status_code == 202, response.text
    return response.json()


async def wait_for_run(client, headers, run_id: str, timeout: float = 60.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(f"api/v1/evaluation-runs/{run_id}", headers=headers)
        assert response.status_code == 200, response.text
        run = response.json()
        if run["status"] in TERMINAL:
            return run
        if asyncio.get_running_loop().time() > deadline:
            pytest.fail(f"run {run_id} did not finish: {run}")
        await asyncio.sleep(0.2)


async def results(client, headers, run_id: str, **params) -> list[dict]:
    response = await client.get(
        f"api/v1/evaluation-runs/{run_id}/results", params={"size": 200, **params}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def eval_message_count() -> int:
    """Chat messages written under an Evals row session (there must never be any)."""
    async with session_scope() as session:
        stmt = select(func.count()).select_from(MessageTable).where(col(MessageTable.session_id).startswith("eval:"))
        return int((await session.exec(stmt)).one())


async def login_headers(client, user) -> dict[str, str]:
    # The user fixtures share this fixed test password; it is not a credential.
    credentials = {"username": user.username, "password": "hashed_password"}  # pragma: allowlist secret
    login = await client.post("api/v1/login", data=credentials)
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
