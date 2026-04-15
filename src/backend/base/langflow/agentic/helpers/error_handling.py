"""Error handling and categorization for the Assistant API."""

MAX_ERROR_MESSAGE_LENGTH = 150
MIN_MEANINGFUL_PART_LENGTH = 10

ERROR_PATTERNS: list[tuple[list[str], str]] = [
    (["rate_limit", "rate limit", "429"], "Rate limit exceeded. Please wait a moment and try again."),
    (["authentication", "api_key", "unauthorized", "401"], "Authentication failed. Check your API key."),
    (["quota", "billing", "insufficient"], "API quota exceeded. Please check your account billing."),
    (["timeout", "timed out"], "Request timed out. Please try again."),
    (["connection", "network"], "Connection error. Please check your network and try again."),
    (["500", "internal server error"], "Server error. Please try again later."),
]


def extract_friendly_error(error_msg: str) -> str:
    """Convert technical API errors into user-friendly messages."""
    error_lower = error_msg.lower()

    for patterns, friendly_message in ERROR_PATTERNS:
        if any(pattern in error_lower or pattern in error_msg for pattern in patterns):
            return friendly_message

    model_missing_terms = ("not found", "does not exist", "not available")
    if "model" in error_lower and any(term in error_lower for term in model_missing_terms):
        return "Model not available. Please select a different model."

    if "content" in error_lower and any(term in error_lower for term in ["filter", "policy", "safety"]):
        return "Request blocked by content policy. Please modify your prompt."

    return _truncate_error_message(error_msg)


def _truncate_error_message(error_msg: str) -> str:
    """Truncate long error messages, preserving meaningful content."""
    if len(error_msg) <= MAX_ERROR_MESSAGE_LENGTH:
        return error_msg

    if ":" in error_msg:
        for part in error_msg.split(":"):
            stripped = part.strip()
            if MIN_MEANINGFUL_PART_LENGTH < len(stripped) < MAX_ERROR_MESSAGE_LENGTH:
                return stripped

    return f"{error_msg[:MAX_ERROR_MESSAGE_LENGTH]}..."
