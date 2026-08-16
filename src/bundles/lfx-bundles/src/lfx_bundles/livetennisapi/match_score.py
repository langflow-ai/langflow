import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.template.field.base import Output

BASE_URL = "https://api.livetennisapi.com/api/public/v1"
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429
PLAYERS_PER_MATCH = 2


def _validated_score(payload: object) -> dict:
    """Return the decoded score object, or raise ``TypeError`` on a malformed 200 payload."""
    if not isinstance(payload, dict):
        msg = "Live Tennis API returned an unexpected response shape (expected a score object)."
        raise TypeError(msg)
    return payload


class LiveTennisMatchScoreComponent(Component):
    display_name = "Match Score"
    description = "Get the current score of one match — sets, games, in-game points and who is serving."
    documentation: str = "https://docs.livetennisapi.com"
    icon = "LiveTennisAPI"
    name = "LiveTennisMatchScore"

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
            name="match_id",
            display_name="Match ID",
            required=True,
            info="The match id — the `id` field on any match returned by the Live Matches or Fixtures component.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Score", name="score", method="fetch_score"),
    ]

    def fetch_score(self) -> Data:
        """Call ``GET /matches/{id}/score`` and return the score snapshot as ``Data``."""
        try:
            match_id = int(str(self.match_id).strip())
        except (TypeError, ValueError):
            error_message = f"Match ID must be an integer, got: {self.match_id!r}"
            logger.error(error_message)
            return Data(text=error_message, data={"error": error_message})

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{BASE_URL}/matches/{match_id}/score",
                    headers={"X-API-Key": self.api_key, "accept": "application/json"},
                )
            response.raise_for_status()
            score = _validated_score(response.json())

            games = score.get("games") or []
            games_str = None
            if len(games) == PLAYERS_PER_MATCH and games[0]:
                games_str = " ".join(f"{g1}-{g2}" for g1, g2 in zip(games[0], games[1], strict=False))
            sets = score.get("sets") or []
            summary_parts = []
            if sets:
                summary_parts.append("sets " + "-".join(str(s) for s in sets))
            if games_str:
                summary_parts.append("games " + games_str)
            summary = ", ".join(summary_parts) or "No score available"

            result = Data(text=summary, data=score)
        except httpx.TimeoutException:
            error_message = "Request timed out (30s). Please try again."
            logger.error(error_message)
            return Data(text=error_message, data={"error": error_message})
        except httpx.HTTPStatusError as exc:
            error_message = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            if exc.response.status_code == HTTP_NOT_FOUND:
                error_message = f"Match {match_id} was not found."
            elif exc.response.status_code == HTTP_TOO_MANY_REQUESTS:
                error_message = "Rate limited. The free tier allows 30 requests/minute and 100/day."
            logger.error(error_message)
            return Data(text=error_message, data={"error": error_message})
        except (httpx.RequestError, ValueError, TypeError) as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return Data(text=error_message, data={"error": error_message})
        else:
            self.status = result
            return result
