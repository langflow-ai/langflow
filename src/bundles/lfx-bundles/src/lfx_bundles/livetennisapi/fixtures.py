import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
HTTP_TOO_MANY_REQUESTS = 429
MIN_LIMIT = 1
MAX_LIMIT = 200
DEFAULT_LIMIT = 50


def _validated_items(payload: object) -> list[dict]:
    """Return the list under ``data``, or raise ``TypeError`` on a malformed 200 payload."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        msg = "Live Tennis API returned an unexpected response shape (expected an object with a 'data' list)."
        raise TypeError(msg)
    items = payload["data"]
    if not all(isinstance(item, dict) for item in items):
        msg = "Live Tennis API returned a malformed 'data' entry (expected objects)."
        raise TypeError(msg)
    return items


class LiveTennisFixturesComponent(Component):
    display_name = "Fixtures"
    description = "List upcoming scheduled tennis fixtures, earliest first, with tournament, round and start time."
    documentation: str = "https://docs.livetennisapi.com"
    icon = "LiveTennisAPI"
    name = "LiveTennisFixtures"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Live Tennis API Key",
            required=True,
            info=(
                "Your Live Tennis API key. The free tier covers live scores, players, "
                "fixtures and usage (30 requests/minute, 100/day)."
            ),
        ),
        DropdownInput(
            name="tour",
            display_name="Tour",
            info="Restrict results to one tour. `all` returns every tour.",
            options=["all", "atp", "wta", "challenger", "itf", "juniors"],
            value="all",
        ),
        IntInput(
            name="limit",
            display_name="Max Results",
            info="Maximum number of fixtures to return (1-200). Out-of-range values are clamped.",
            value=50,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Fixtures", name="fixtures", method="fetch_fixtures_dataframe"),
    ]

    def _clamped_limit(self) -> int:
        """Clamp the limit input to the API's documented 1-200 range."""
        try:
            limit = int(self.limit)
        except (TypeError, ValueError):
            return DEFAULT_LIMIT
        return max(MIN_LIMIT, min(MAX_LIMIT, limit))

    def fetch_fixtures(self) -> list[Data]:
        """Call ``GET /fixtures`` and return one ``Data`` row per fixture, or a single error row."""
        try:
            params: dict = {"limit": self._clamped_limit()}
            if self.tour and self.tour != "all":
                params["tour"] = self.tour

            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{BASE_URL}/fixtures",
                    params=params,
                    headers={"X-API-Key": self.api_key, "accept": "application/json"},
                )
            response.raise_for_status()

            results = []
            for fixture in _validated_items(response.json()):
                row = {
                    "id": fixture.get("id"),
                    "event_date": fixture.get("event_date"),
                    "start_time": fixture.get("start_time"),
                    "tournament": fixture.get("tournament"),
                    "round": fixture.get("round"),
                    "round_code": fixture.get("round_code"),
                    "tour": fixture.get("tour"),
                    "surface": fixture.get("surface"),
                    "player1_name": fixture.get("player1_name"),
                    "player1_id": fixture.get("player1_id"),
                    "player2_name": fixture.get("player2_name"),
                    "player2_id": fixture.get("player2_id"),
                    "status": fixture.get("status"),
                }
                summary = f"{row.get('player1_name')} vs {row.get('player2_name')} — {row.get('tournament')}"
                results.append(Data(text=summary, data=row))
        except httpx.TimeoutException:
            error_message = "Request timed out (30s). Please try again."
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except httpx.HTTPStatusError as exc:
            error_message = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            if exc.response.status_code == HTTP_TOO_MANY_REQUESTS:
                error_message = "Rate limited. The free tier allows 30 requests/minute and 100/day."
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except (httpx.RequestError, ValueError, TypeError) as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        else:
            self.status = results
            return results

    def fetch_fixtures_dataframe(self) -> DataFrame:
        """Return the fixtures as a ``DataFrame`` (one row per fixture)."""
        data = self.fetch_fixtures()
        return DataFrame(data)
