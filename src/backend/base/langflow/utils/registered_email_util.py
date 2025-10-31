from lfx.log.logger import logger

from langflow.api.v2.registration import load_registration


class _Registration:
    # Static variable
    # Tri-state:
    # - str (empty): Load registration not invoked yet
    # - str (non-empty): Load registration invoked (valid registered email address)
    # - None: Load registration invoked (no registered email address or error encountered)
    _email = ""

    @classmethod
    def get_email(cls) -> str | None:
        return cls._email

    @classmethod
    def set_email(cls, value: str | None):
        cls._email = value


def get_email() -> str:
    """Retrieves the registered email address."""
    # Use cached email address from a previous invocation (if applicable)
    email = _Registration.get_email()

    if email is None:
        # No registered email address or error encountered
        return ""

    if email:
        # Non-empty email address
        return email

    # Empty email address ("")
    # Retrieve registration
    try:
        registration = load_registration()
    except (OSError, UnicodeDecodeError, AttributeError) as e:
        _Registration.set_email(None)
        logger.error(f"Failed to load registration: {e}")
        return ""

    # Parse email address from registration
    email = _parse_email(registration)

    # Cache email address
    if email:
        _Registration.set_email(email)
    else:
        _Registration.set_email(None)

    return email


def _parse_email(registration) -> str:
    """Parses the email address from the registration."""
    # Verify registration is a dict
    if not isinstance(registration, dict):
        logger.error("Email registration is not a valid dict.")
        return ""

    # Retrieve email address
    email = registration.get("email")

    # Verify email address is a valid non-zero length string
    if not isinstance(email, str) or (len(email) == 0):
        logger.error(f"Email registration is not a valid non-zero length string: {email}.")
        return ""
    return email
