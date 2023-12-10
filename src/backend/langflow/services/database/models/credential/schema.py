from enum import Enum


class CredentialType(str, Enum):
    """CredentialType is an Enum of the accepted providers"""

    OPENAI_API_KEY = "OPENAI_API_KEY"
    ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
