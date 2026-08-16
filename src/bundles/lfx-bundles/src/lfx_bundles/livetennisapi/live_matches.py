import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
HTTP_TOO_MANY_REQUESTS = 429
PLAYERS_PER_MATCH = 2
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


class LiveTennisMatchesComponent(Component):
    display_name = "Live Matches"
    description = (
        "List live or upcoming tennis matches across ATP, WTA, Challenger, ITF "
        "and juniors, with the current score on each match."
    )
    documentation: str = "https://docs.livetennisapi.com"
    icon = "LiveTennisAPI"
    name = "LiveTennisMatches"

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
            name="match_status",
            display_name="Status",
            info=(
                "Match lifecycle status. `live` and `upcoming` are available on the "
                "free tier; completed-match history is a separate paid surface and "
                "is not offered by this component."
            ),
            options=["live", "upcoming"],
            value="live",
        ),
        DropdownInput(
            name="tour",
            display_name="Tour",
            info="Restrict results to one tour. `all` returns every tour.",
            options=["all", "atp", "wta", "challenger", "itf", "juniors"],
            value="all",
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Max Results",
            info="Maximum number of matches to return (1-200). Out-of-range values are clamped.",
            value=50,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Matches", name="matches", method="fetch_matches_dataframe"),
    ]

    def _clamped_limit(self) -> int:
        """Clamp the limit input to the API's documented 1-200 range."""
        try:
            limit = int(self.limit)
        except (TypeError, ValueError):
            return DEFAULT_LIMIT
        return max(MIN_LIMIT, min(MAX_LIMIT, limit))

    def _flatten_match(self, match: dict) -> dict:
        """Flatten one match object into a single-level row for the DataFrame output."""
        players = match.get("players") or {}
        p1 = players.get("p1") or {}
        p2 = players.get("p2") or {}
        score = match.get("score") or {}
        sets = score.get("sets") or []
        games = score.get("games") or []
        points = score.get("points") or []

        games_str = None
        if len(games) == PLAYERS_PER_MATCH and games[0]:
            games_str = " ".join(f"{g1}-{g2}" for g1, g2 in zip(games[0], games[1], strict=False))

        return {
            "id": match.get("id"),
            "status": match.get("status"),
            "tour": match.get("tour"),
            "tournament": match.get("tournament"),
            "tournament_id": match.get("tournament_id"),
            "round": match.get("round"),
            "surface": match.get("surface"),
            "format": match.get("format"),
            "is_doubles": match.get("is_doubles"),
            "scheduled_time": match.get("scheduled_time"),
            "player1": p1.get("name"),
            "player1_id": p1.get("id"),
            "player1_country": p1.get("country"),
            "player1_ranking": p1.get("ranking"),
            "player2": p2.get("name"),
            "player2_id": p2.get("id"),
            "player2_country": p2.get("country"),
            "player2_ranking": p2.get("ranking"),
            "sets": "-".join(str(s) for s in sets) if sets else None,
            "games": games_str,
            "points": "-".join(str(p) for p in points) if points else None,
            "server": score.get("server"),
        }

    def fetch_matches(self) -> list[Data]:
        """Call ``GET /matches`` and return one ``Data`` row per match, or a single error row."""
        try:
            params: dict = {"status": self.match_status, "limit": self._clamped_limit()}
            if self.tour and self.tour != "all":
                params["tour"] = self.tour

            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{BASE_URL}/matches",
                    params=params,
                    headers={"X-API-Key": self.api_key, "accept": "application/json"},
                )
            response.raise_for_status()

            results = []
            for match in _validated_items(response.json()):
                row = self._flatten_match(match)
                summary = f"{row.get('player1')} vs {row.get('player2')} — {row.get('tournament')}"
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

    def fetch_matches_dataframe(self) -> DataFrame:
        """Return the matches as a ``DataFrame`` (one row per match)."""
        data = self.fetch_matches()
        return DataFrame(data)
