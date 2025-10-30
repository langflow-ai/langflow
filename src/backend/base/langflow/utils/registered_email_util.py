import json

from lfx.log.logger import logger

from langflow.api.v2.registration import load_registrations


def get_registered_email_address() -> str:
    """Retrieves the registered email address."""
    try:
        # Retrieve registrations
        registrations = load_registrations()

        # Verify registrations is a valid non-zero length list
        if not isinstance(registrations, list) or (len(registrations) == 0):
            logger.error("Email registrations is not a valid non-zero length list.")
            return ""

        # Retrieve the first registration only (there can only be one valid email registration)
        email_registration = registrations[0]

        # Verify registration is a dict
        if not isinstance(email_registration, dict):
            logger.error("Email registration is not a valid dict.")
            return ""

        # Retrieve email address
        email = email_registration.get("email")

        # Verify email address is a valid non-zero length string
        if not isinstance(email, str) or (len(email) == 0):
            logger.error(f"Email registration is not a valid non-zero length string: {email}.")
            return ""

        return email  # noqa: TRY300

    except json.JSONDecodeError as e:
        logger.error(f"Unable to load email registrations: {e}.")
        return ""
    except PermissionError as e:
        logger.error(f"Unable to load email registrations: {e}.")
        return ""
    except OSError as e:
        logger.error(f"Unable to load email registrations: {e}.")
        return ""
