import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
HTTP_TOO_MANY_REQUESTS = 429


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
            info="Maximum number of players to return (1-200).",
            value=50,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Players", name="players", method="fetch_players_dataframe"),
    ]

    def fetch_players(self) -> list[Data]:
        try:
            params: dict = {"limit": self.limit}
            if self.search:
                params["search"] = self.search

            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{BASE_URL}/players",
                    params=params,
                    headers={"X-API-Key": self.api_key, "accept": "application/json"},
                )
            response.raise_for_status()
            payload = response.json()

            results = []
            for player in payload.get("data", []):
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
        except (httpx.RequestError, ValueError) as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        else:
            self.status = results
            return results

    def fetch_players_dataframe(self) -> DataFrame:
        data = self.fetch_players()
        return DataFrame(data)
