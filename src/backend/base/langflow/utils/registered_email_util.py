from lfx.log.logger import logger

from langflow.api.v2.registration import load_registration
from langflow.services.telemetry.schema import EmailPayload


class _RegisteredEmailCache:
    """An in-memory cache for the registered email address."""

    # Static variable
    _email_model: EmailPayload | None = None

    # Static variable
    # - True: Registered email address has been resolved via a downstream source (either defined or not defined)
    # - False: Registered email address has not been resolved yet
    _resolved: bool = False

    @classmethod
    def get_email_model(cls) -> EmailPayload | None:
        """Retrieves the registered email address from the cache."""
        return cls._email_model

    @classmethod
    def set_email_model(cls, value: EmailPayload | None) -> None:
        """Stores the registered email address in the cache."""
        cls._email_model = value
        cls._resolved = True

    @classmethod
    def is_resolved(cls) -> bool:
        """Determines whether the registered email address was resolved from a downstream source."""
        return cls._resolved


def get_email_model() -> EmailPayload | None:
    """Retrieves the registered email address model."""
    # Fast path: direct class attr read to minimize indirection
    _cache = _RegisteredEmailCache
    email = _cache._email_model
    if email is not None:
        return email
    if _cache._resolved:
        # No registered email address
        # OR an email address parsing error occurred
        return None

    # Retrieve registration
    try:
        registration = load_registration()
    except (OSError, UnicodeDecodeError, AttributeError) as e:
        _cache.set_email_model(None)
        logger.error(f"Failed to load registration: {e}")
        return None

    # Parse email address from registration
    email_model = _parse_email_registration(registration)
    _cache.set_email_model(email_model)

    return email_model


def _parse_email_registration(registration) -> EmailPayload | None:
    """Parses the email address from the registration."""
    # Verify registration is a dict
    if not isinstance(registration, dict):
        logger.error("Email registration is not a valid dict.")
        return None

    # Retrieve email address
    email = registration.get("email")
    return _create_email_model(email)


def _create_email_model(email) -> EmailPayload | None:
    """Creates the model for the registered email."""
    # Verify email address is a valid non-zero length string
    if not isinstance(email, str) or (len(email) == 0):
        logger.error(f"Email is not a valid non-zero length string: {email}.")
        return None

    # Verify email address is syntactically valid
    email_model: EmailPayload | None = None

    try:
        email_model = EmailPayload(email=email)
    except ValueError as err:
        logger.error(f"Email is not a valid email address: {email}: {err}.")
        return None

    return email_model
