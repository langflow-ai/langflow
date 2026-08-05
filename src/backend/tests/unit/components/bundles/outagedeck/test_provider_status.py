import httpx
import pytest
import respx
from httpx import Response

pytest.importorskip("lfx_bundles")

from lfx.schema.data import Data
from lfx_bundles.outagedeck.provider_status import OUTAGEDECK_API_BASE_URL, OutageDeckProviderStatusComponent

from tests.base import ComponentTestBaseWithoutClient


class TestOutageDeckProviderStatusComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return OutageDeckProviderStatusComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"provider_slug": "github"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_frontend_metadata(self, component_class):
        component = component_class()
        node = component.to_frontend_node()["data"]["node"]

        assert node["display_name"] == "Provider Status"
        assert node["icon"] == "OutageDeck"
        assert node["template"]["provider_slug"]["tool_mode"] is True
        assert "utm_campaign=langflow_provider_status" in node["documentation"]

    @respx.mock
    async def test_get_provider_status_success(self, component_class):
        payload = {
            "meta": {"version": "v1", "generatedAt": "2026-08-05T12:00:00Z"},
            "data": {
                "slug": "github",
                "name": "GitHub",
                "currentStatus": {
                    "code": "operational",
                    "label": "Operational",
                    "headline": "All Systems Operational",
                },
                "services": [],
                "activeIncidents": [],
                "source": {"statusPageUrl": "https://www.githubstatus.com"},
            },
        }
        route = respx.get(f"{OUTAGEDECK_API_BASE_URL}/github").mock(return_value=Response(200, json=payload))
        component = component_class(provider_slug=" GitHub ")

        result = await component.get_provider_status()

        assert isinstance(result, Data)
        assert result.data == payload
        assert component.status == "GitHub: Operational — All Systems Operational"
        assert route.called
        assert route.calls.last.request.headers["accept"] == "application/json"
        assert route.calls.last.request.headers["user-agent"] == "Langflow-OutageDeck/1.0"

    @respx.mock
    async def test_invalid_slug_is_rejected_before_request(self, component_class):
        component = component_class(provider_slug="../incidents")

        result = await component.get_provider_status()

        assert "Provider slug must contain" in result.data["error"]
        assert not respx.calls.called

    @respx.mock
    async def test_unknown_provider_returns_clear_error(self, component_class):
        respx.get(f"{OUTAGEDECK_API_BASE_URL}/unknown-provider").mock(return_value=Response(404))
        component = component_class(provider_slug="unknown-provider")

        result = await component.get_provider_status()

        assert result.data == {"error": "OutageDeck does not have a provider with slug 'unknown-provider'."}

    @respx.mock
    async def test_network_failure_returns_retryable_error(self, component_class):
        respx.get(f"{OUTAGEDECK_API_BASE_URL}/github").mock(side_effect=httpx.ConnectError("offline"))
        component = component_class(provider_slug="github")

        result = await component.get_provider_status()

        assert result.data == {"error": "Could not reach OutageDeck. Try the provider status request again."}

    @respx.mock
    async def test_unexpected_response_shape_returns_error(self, component_class):
        respx.get(f"{OUTAGEDECK_API_BASE_URL}/github").mock(return_value=Response(200, json={"data": []}))
        component = component_class(provider_slug="github")

        result = await component.get_provider_status()

        assert result.data == {"error": "OutageDeck returned an unexpected response shape."}

    @pytest.mark.asyncio
    async def test_latest_version(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component is not None
