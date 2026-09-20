import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
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


class LiveTennisPlayerSearchComponent(Component):
    display_name = "Player Search"
    description = (
        "Search tennis players by name across ATP, WTA, Challenger, ITF and "
        "juniors. Returns bio, country and current ranking, ranked players first."
    )
    documentation: str = "https://docs.livetennisapi.com"
    icon = "LiveTennisAPI"
    name = "LiveTennisPlayerSearch"

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
        MessageTextInput(
            name="search",
            display_name="Search",
            info="Player name to search for. Leave empty to list players, ranked first.",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Max Results",
            info="Maximum number of players to return (1-200). Out-of-range values are clamped.",
            value=50,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Players", name="players", method="fetch_players_dataframe"),
    ]

    def _clamped_limit(self) -> int:
        """Clamp the limit input to the API's documented 1-200 range."""
        try:
            limit = int(self.limit)
        except (TypeError, ValueError):
            return DEFAULT_LIMIT
        return max(MIN_LIMIT, min(MAX_LIMIT, limit))

    def fetch_players(self) -> list[Data]:
        """Call ``GET /players`` and return one ``Data`` row per player, or a single error row."""
        try:
            params: dict = {"limit": self._clamped_limit()}
            if self.search:
                params["search"] = self.search

            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{BASE_URL}/players",
                    params=params,
                    headers={"X-API-Key": self.api_key, "accept": "application/json"},
                )
            response.raise_for_status()

            results = []
            for player in _validated_items(response.json()):
                row = {
                    "id": player.get("id"),
                    "name": player.get("name"),
                    "tour": player.get("tour"),
                    "country": player.get("country"),
                    "ranking": player.get("ranking"),
                    "ranking_points": player.get("ranking_points"),
                    "ranking_movement": player.get("ranking_movement"),
                    "hand": player.get("hand"),
                    "birthday": player.get("birthday"),
                    "is_doubles_team": player.get("is_doubles_team"),
                }
                results.append(Data(text=str(row.get("name")), data=row))
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

    def fetch_players_dataframe(self) -> DataFrame:
        """Return the players as a ``DataFrame`` (one row per player)."""
        data = self.fetch_players()
        return DataFrame(data)
