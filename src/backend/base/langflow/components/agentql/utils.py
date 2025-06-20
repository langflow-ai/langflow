import httpx
from loguru import logger

QUERY_DOCS_URL = "https://docs.agentql.com/agentql-query"
QUERY_DATA_API_DOCS_URL = "https://docs.agentql.com/rest-api/api-reference#query-data"
QUERY_DOCUMENT_API_DOCS_URL = "https://docs.agentql.com/rest-api/api-reference#query-document"

MISSING_REQUIRED_INPUTS_MESSAGE = "Either Query or Prompt must be provided."
TOO_MANY_INPUTS_MESSAGE = "Both Query and Prompt can't be provided at the same time."
INVALID_API_KEY_MESSAGE = "Please, provide a valid API Key. You can create one at https://dev.agentql.com."


def handle_agentql_error(e: httpx.HTTPStatusError) -> str:
    """Handle AgentQL API errors and return appropriate error message."""
    response = e.response
    if response.status_code == httpx.codes.UNAUTHORIZED:
        return INVALID_API_KEY_MESSAGE
    try:
        error_json = response.json()
        logger.error(f"Failure response: '{response.status_code} {response.reason_phrase}' with body: {error_json}")
        return error_json.get("error_info") or error_json.get("detail")
    except (ValueError, TypeError):
        return f"HTTP {e}."
