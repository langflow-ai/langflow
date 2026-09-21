import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langflow.services.store.schema import StoreComponentCreate
from langflow.services.store.service import StoreService

LITERAL_SECRET = "sk-PLANTED-MARKER-DO-NOT-USE-1234567890"  # noqa: S105  # pragma: allowlist secret


def _make_component(*, load_from_db: bool, value: str) -> StoreComponentCreate:
    return StoreComponentCreate(
        name="poc-leaky-component",
        description="planted credential in a password field",
        data={
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {
                                    "name": "api_key",
                                    "password": True,
                                    "load_from_db": load_from_db,
                                    "value": value,
                                }
                            }
                        }
                    }
                }
            ],
            "edges": [],
        },
        tags=None,
        is_component=True,
        private=True,
    )


def _make_service() -> StoreService:
    settings = SimpleNamespace(
        store_url="https://store.example.test",
        download_webhook_url=None,
        like_webhook_url=None,
    )
    return StoreService(SimpleNamespace(settings=settings))


@pytest.fixture
def captured_request(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["json"] = json.loads(request.content)
        return httpx.Response(201, json={"data": {"id": str(uuid4())}})

    real_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr("langflow.services.store.service.httpx.AsyncClient", client_factory)
    return captured


async def test_upload_strips_literal_secret_field_values(captured_request):
    service = _make_service()
    component = _make_component(load_from_db=False, value=LITERAL_SECRET)

    await service.upload("store-api-key", component)

    sent_value = captured_request["json"]["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]
    assert sent_value is None
    assert LITERAL_SECRET not in json.dumps(captured_request["json"])
    # The caller's payload must not be mutated by the redaction.
    original_value = component.data["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]
    assert original_value == LITERAL_SECRET


async def test_update_strips_literal_secret_field_values(captured_request):
    service = _make_service()
    component = _make_component(load_from_db=False, value=LITERAL_SECRET)

    await service.update("store-api-key", uuid4(), component)

    sent_value = captured_request["json"]["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]
    assert sent_value is None
    assert LITERAL_SECRET not in json.dumps(captured_request["json"])


async def test_upload_preserves_global_variable_reference(captured_request):
    service = _make_service()
    component = _make_component(load_from_db=True, value="MY_GLOBAL_VARIABLE")

    await service.upload("store-api-key", component, known_variable_names={"MY_GLOBAL_VARIABLE"})

    sent_value = captured_request["json"]["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]
    assert sent_value == "MY_GLOBAL_VARIABLE"


async def test_upload_nulls_name_shaped_literal_outside_known_variables(captured_request):
    service = _make_service()
    component = _make_component(load_from_db=True, value="PROD_DB_PASSWORD")

    await service.upload("store-api-key", component, known_variable_names={"OTHER_VARIABLE"})

    sent_value = captured_request["json"]["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]
    assert sent_value is None


async def test_update_preserves_global_variable_reference(captured_request):
    service = _make_service()
    component = _make_component(load_from_db=True, value="MY_GLOBAL_VARIABLE")

    await service.update("store-api-key", uuid4(), component, known_variable_names={"MY_GLOBAL_VARIABLE"})

    sent_value = captured_request["json"]["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]
    assert sent_value == "MY_GLOBAL_VARIABLE"


async def test_upload_strips_credential_shaped_value_behind_load_from_db(captured_request):
    service = _make_service()
    component = _make_component(load_from_db=True, value=LITERAL_SECRET)

    await service.upload("store-api-key", component)

    sent_value = captured_request["json"]["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]["value"]
    assert sent_value is None
