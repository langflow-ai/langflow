"""The editor refreshes WhatsApp metadata under its authenticated identity."""

import inspect
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import lfx_whatsapp
import pytest
from lfx.custom.utils import create_component_template
from lfx.extension.bundle_registry import BundleRecord, get_default_registry
from lfx.extension.loader._types import LoadedIntegration
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.integrations.errors import ConnectionNotAuthorizedError
from lfx.integrations.models import ConnectionAccount, ResolvedCredential
from lfx.services.integration_policy import IntegrationPolicyService
from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot
from lfx_whatsapp import WhatsAppSendTemplateComponent
from lfx_whatsapp._client import SCOPES
from pydantic import SecretStr

pytestmark = pytest.mark.no_blockbuster

TOKEN = "synthetic-whatsapp-template-refresh-token"  # noqa: S105  # pragma: allowlist secret


@pytest.fixture
def template_refresh(monkeypatch, client):  # noqa: ARG001
    for key, value in {
        "APP_ID": "111",
        "WABA_ID": "222",
        "PHONE_ID": "333",
        "GRAPH_VERSION": "v25.0",
        "APP_SECRET": "a" * 32,
    }.items():
        monkeypatch.setenv("LANGFLOW_WHATSAPP_" + key, value)
    registry = get_default_registry()
    bundle_name = "whatsapp_template_refresh_test"
    installed = any(item.provider_id == "whatsapp" for item in registry.list_integrations())
    if not installed:
        path = Path(lfx_whatsapp.__file__).parent / "components/whatsapp/capabilities.v1.json"
        registry.install_bundle(
            BundleRecord(
                bundle=bundle_name,
                extension_id="lfx-whatsapp-template-test",
                extension_version="0.1.1",
                slot="extra",
                integrations=(
                    LoadedIntegration(
                        extension_id="lfx-whatsapp-template-test",
                        extension_version="0.1.1",
                        bundle=bundle_name,
                        provider_id="whatsapp",
                        manifest_path=path,
                        capability_manifest=IntegrationCapabilityManifest.model_validate_json(path.read_text()),
                    ),
                ),
            )
        )
    state = SimpleNamespace(resolutions=[], requests=[], deny=False)

    class Resolver:
        async def resolve(self, request):
            state.resolutions.append(request)
            if state.deny:
                raise ConnectionNotAuthorizedError(provider="whatsapp")
            return ResolvedCredential(
                access_token=SecretStr(TOKEN),
                provider="whatsapp",
                identity="service",
                owner_kind="user",
                account=ConnectionAccount(id="333", tenant_id="111:222"),
                granted_scopes=frozenset(SCOPES),
                scopes_verified=True,
            )

    def handle(request):
        state.requests.append(request)
        assert request.method == "GET"
        if request.url.path.endswith("/debug_token"):
            body = {
                "data": {
                    "is_valid": True,
                    "type": "SYSTEM_USER",
                    "app_id": "111",
                    "expires_at": 0,
                    "scopes": list(SCOPES),
                }
            }
        elif request.url.path.endswith("/222/phone_numbers"):
            body = {"data": [{"id": "333"}]}
        else:
            assert request.url.path == "/v25.0/222/message_templates"
            body = {
                "data": [
                    {
                        "name": "order_update",
                        "language": "pt_BR",
                        "status": "APPROVED",
                        "components": [{"type": "BODY", "text": "Order {{1}} for {{2}}"}],
                    }
                ]
            }
        return httpx.Response(200, json=body)

    client_httpx = SimpleNamespace(**vars(httpx))
    client_httpx.AsyncHTTPTransport = lambda **_kwargs: httpx.MockTransport(handle)
    monkeypatch.setattr("lfx_whatsapp._client.httpx", client_httpx)
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: Resolver())
    yield state
    if not installed:
        registry.remove_bundle(bundle_name)


def _request():
    source = Path(inspect.getsourcefile(WhatsAppSendTemplateComponent)).read_text()
    component = WhatsAppSendTemplateComponent(
        _code=source, connection="whatsapp/business", template_name="order_update", language="en_US"
    )
    frontend, _ = create_component_template(component_extractor=component)
    frontend["metadata"]["component_class_name"] = "WhatsAppSendTemplateComponent"
    return {
        "code": source,
        "frontend_node": frontend,
        "template": frontend["template"],
        "field": "connection",
        "field_value": "whatsapp/business",
    }


async def test_refresh_uses_authenticated_actor_and_returns_only_template_metadata(
    client, logged_in_headers, active_user, template_refresh
):
    response = await client.post("api/v1/custom_component/update", json=_request(), headers=logged_in_headers)

    assert response.status_code == 200, response.text
    fields = response.json()["template"]
    assert fields["template_name"]["options"] == ["order_update"]
    assert fields["language"]["options"] == ["pt_BR"]
    assert fields["language"]["value"] == "pt_BR"
    assert "2 positional" in fields["body_parameters"]["info"]
    assert TOKEN not in response.text
    assert template_refresh.resolutions
    assert all(
        request.principal.kind == "actor"
        and request.principal.user_id == str(active_user.id)
        and request.principal.interactive
        and request.capability_ids == frozenset({"whatsapp.template.send"})
        for request in template_refresh.resolutions
    )
    assert len(template_refresh.requests) == 3


async def test_unauthenticated_refresh_does_not_resolve_a_connection(client, template_refresh):
    response = await client.post("api/v1/custom_component/update", json=_request())

    assert response.status_code in {401, 403}
    assert template_refresh.resolutions == []
    assert template_refresh.requests == []


async def test_connection_denial_does_not_call_meta(client, logged_in_headers, template_refresh):
    template_refresh.deny = True

    response = await client.post("api/v1/custom_component/update", json=_request(), headers=logged_in_headers)

    assert response.status_code == 400, response.text
    assert template_refresh.resolutions
    assert template_refresh.requests == []


@pytest.mark.parametrize("blocked", ["provider", "action"])
async def test_blocked_refresh_does_not_resolve_credentials(
    client, logged_in_headers, template_refresh, monkeypatch, blocked
):
    bundle = PolicyBundleService()
    bundle.publish(
        PolicyBundleSnapshot(
            revision=1,
            approved_integration_provider_ids=frozenset({"slack"}) if blocked == "provider" else None,
            blocked_integration_action_keys=frozenset({"integrations.whatsapp.template.send"})
            if blocked == "action"
            else frozenset(),
        )
    )
    service = IntegrationPolicyService(policy_bundle_service=bundle)
    monkeypatch.setattr("lfx.services.deps.get_integration_policy_service", lambda: service)

    response = await client.post("api/v1/custom_component/update", json=_request(), headers=logged_in_headers)

    assert response.status_code == 404, response.text
    assert template_refresh.resolutions == []
    assert template_refresh.requests == []


async def test_template_cannot_replace_the_authenticated_user_id(client, logged_in_headers, template_refresh):
    request = _request()
    request["template"]["_user_id"] = {"_input_type": "StrInput", "value": str(uuid4())}

    response = await client.post("api/v1/custom_component/update", json=request, headers=logged_in_headers)

    assert response.status_code == 400, response.text
    assert "reserved word" in response.json()["detail"]
    assert template_refresh.resolutions == []
    assert template_refresh.requests == []
