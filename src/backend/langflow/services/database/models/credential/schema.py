from enum import Enum


class AcceptedProviders(str, Enum):
    """Accepted providers for credentials."""

    openai = "openai"
    anthropic = "anthropic"
