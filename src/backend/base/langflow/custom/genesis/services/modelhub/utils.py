import base64
import json
import time


def is_token_expired(token: str) -> bool:
    """Checks whether a JWT token has expired.

    Args:
        token (str): JWT token.

    Returns:
        bool: True if expired, otherwise False.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format.")

    payload = base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8")
    expiration = json.loads(payload)["exp"]
    return expiration < time.time()
