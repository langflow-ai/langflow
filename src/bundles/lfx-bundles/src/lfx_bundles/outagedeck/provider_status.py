import re

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

OUTAGEDECK_API_BASE_URL = "https://outagedeck.com/api/v1/providers"
PROVIDER_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OutageDeckProviderStatusComponent(Component):
    display_name = "Provider Status"
    description = (
        "Retrieves keyless, read-only cloud and SaaS provider status, incidents, services, freshness, and source links."
    )
    documentation = (
        "https://outagedeck.com/developers/api?utm_source=langflow&utm_medium=integration&"
        "utm_campaign=langflow_provider_status"
    )
    icon = "OutageDeck"
    name = "OutageDeckProviderStatus"

    inputs = [
        MessageTextInput(
            name="provider_slug",
            display_name="Provider Slug",
            info="The OutageDeck provider slug, such as github, aws, cloudflare, or openai.",
            value="github",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Provider Status", name="provider_status", method="get_provider_status"),
    ]

    def _error(self, message: str) -> Data:
        self.status = message
        return Data(data={"error": message})

    async def get_provider_status(self) -> Data:
        slug = str(self.provider_slug or "").strip().lower()
        if not PROVIDER_SLUG_PATTERN.fullmatch(slug):
            return self._error(
                "Provider slug must contain only lowercase letters, numbers, and single hyphens, such as github or aws."
            )

        url = f"{OUTAGEDECK_API_BASE_URL}/{slug}"
        headers = {"Accept": "application/json", "User-Agent": "Langflow-OutageDeck/1.0"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.NOT_FOUND:
                return self._error(f"OutageDeck does not have a provider with slug '{slug}'.")
            return self._error(f"OutageDeck returned HTTP {exc.response.status_code} for provider '{slug}'.")
        except httpx.RequestError:
            return self._error("Could not reach OutageDeck. Try the provider status request again.")
        except ValueError:
            return self._error("OutageDeck returned a response that was not valid JSON.")

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            return self._error("OutageDeck returned an unexpected response shape.")

        provider = payload["data"]
        status_value = provider.get("currentStatus")
        current_status = status_value if isinstance(status_value, dict) else {}
        name = provider.get("name") or slug
        label = current_status.get("label", current_status.get("code", "Unknown"))
        headline = current_status.get("headline", "No status headline")
        self.status = f"{name}: {label} — {headline}"
        return Data(data=payload)
