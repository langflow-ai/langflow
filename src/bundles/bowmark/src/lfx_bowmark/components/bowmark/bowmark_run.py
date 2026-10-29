import json

import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import IntInput, MultilineInput, SecretStrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from . import _client

RUN_ENDPOINT = f"{_client.API_BASE}/v1/run"
DEFAULT_TIMEOUT = 180


class BowmarkRunComponent(Component):
    """Run a short Bowmark script against live websites and return the result."""

    display_name = "Bowmark Run"
    description = (
        "Run a short JavaScript script that calls Bowmark functions (found with Bowmark Library) "
        "and return its result. Example: return (await bowmark.providers.hackernews.topStories()).slice(0, 3)"
    )
    documentation = "https://bowmark.ai"
    icon = "globe"

    inputs = [
        MultilineInput(
            name="script",
            display_name="Script",
            required=True,
            info="JavaScript body that returns a value, using the bowmark.* functions from Bowmark Library.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="bowmark_api_key",
            display_name="Bowmark API Key",
            required=True,
            info="Your Bowmark API key. Get one at https://bowmark.ai.",
            password=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=DEFAULT_TIMEOUT,
            required=False,
            advanced=True,
            info="How long to wait for the run to finish.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode; keep it specific.
        Output(display_name="Result", name="result", method="bowmark_run"),
    ]

    def _run(self) -> dict:
        api_key = _client.require_key(self.bowmark_api_key)
        if not (self.script or "").strip():
            msg = "Script is required."
            raise ValueError(msg)
        timeout = DEFAULT_TIMEOUT if not self.timeout else int(self.timeout)
        response = httpx.post(
            RUN_ENDPOINT,
            json={"script": self.script},
            headers=_client.headers(api_key),
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def _error(self, message: str) -> Data:
        data = Data(text=message, data={"error": message})
        self.status = data
        return data

    def bowmark_run(self) -> Data:
        """Run the script and return its result, run id and logs."""
        try:
            payload = self._run()
        except httpx.HTTPStatusError as e:
            return self._error(_client.http_error_message(e))
        except (httpx.HTTPError, ValueError) as e:
            return self._error(str(e))

        if not isinstance(payload, dict):
            return self._error("Bowmark returned an unexpected response (expected a JSON object).")
        if payload.get("status") == "needs_user":
            # A site needs the user to sign in. Not a failure: hand back the single-use
            # link; after signing in, run the same script again.
            handoff = (payload.get("meta") or {}).get("handoff") or {}
            url = handoff.get("url")
            needs = payload.get("needs") or []
            data = Data(
                text=f"Sign-in needed to continue. Open {url}, sign in, then run again.",
                data={
                    "status": "needs_user",
                    "handoff_url": url,
                    "needs": needs,
                    "run_id": payload.get("runId"),
                },
            )
            self.status = data
            return data
        if not payload.get("ok", False):
            error = payload.get("error") or payload.get("status") or "run failed"
            if isinstance(error, dict):
                error = error.get("message") or json.dumps(error)
            return self._error(f"Bowmark run failed: {error} (runId {payload.get('runId')})")

        result = payload.get("result")
        text = result if isinstance(result, str) else json.dumps(result, default=str)
        data = Data(
            text=text,
            data={
                "result": result,
                "status": payload.get("status"),
                "run_id": payload.get("runId"),
                "logs": payload.get("logs") or [],
            },
        )
        self.status = data
        return data
