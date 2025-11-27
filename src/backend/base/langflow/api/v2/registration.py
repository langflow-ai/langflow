import json
from asyncio import to_thread
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from langflow.logging import logger
from langflow.services.deps import get_telemetry_service
from langflow.services.telemetry.schema import EmailPayload

router = APIRouter(tags=["Registration API"], prefix="/registration")


# Data model for registration
class RegisterRequest(BaseModel):
    email: EmailStr


class RegisterResponse(BaseModel):
    email: str


# File to store registrations
REGISTRATION_FILE = Path("data/user/registration.json")


def _ensure_registration_file():
    """Ensure registration file and directory exist with proper permissions."""
    try:
        # Ensure the directory exists with secure permissions
        REGISTRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Set directory permissions to owner read/write/execute only (if possible)
        REGISTRATION_FILE.parent.chmod(0o700)
    except Exception as e:
        logger.error(f"Failed to create registration file/directory: {e}")
        raise


# TODO: Move functions to a separate service module


def load_registration() -> dict | None:
    """Load the single registration from file."""
    if not REGISTRATION_FILE.exists() or REGISTRATION_FILE.stat().st_size == 0:
        return None
    try:
        with REGISTRATION_FILE.open("rb") as f:  # using binary mode for faster file IO
            content = f.read()
        return json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.error(f"Corrupted registration file: {REGISTRATION_FILE}")
        return None


def save_registration(email: str) -> bool:
    """Save the single registration to file.

    Args:
        email: Email to register

    Returns:
        True if saved successfully
    """
    try:
        # Ensure the registration file and directory exist
        _ensure_registration_file()

        # Check if registration already exists
        existing = load_registration()

        # Create new registration (replaces any existing)
        registration = {
            "email": email,
            "registered_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        # Log if replacing
        if existing:
            logger.info(f"Replacing registration: {existing.get('email')} -> {email}")

        # Save to file
        with REGISTRATION_FILE.open("w") as f:
            json.dump(registration, f, indent=2)

        logger.info(f"Registration saved: {email}")

    except Exception as e:
        logger.error(f"Error saving registration: {e}")
        raise
    else:
        return True


@router.post("/", response_model=RegisterResponse)
async def register_user(request: RegisterRequest):
    """Register the single user with email.

    Note: Only one registration is allowed.
    """
    try:
        email = request.email
        # Save to local file (replace existing) not dealing with 201 status for simplicity.
        if await to_thread(save_registration, email):
            await _send_email_telemetry(email=email)
            return RegisterResponse(email=email)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e!s}") from e


async def _send_email_telemetry(email: str) -> None:
    """Send the telemetry event for the registered email address."""
    payload: EmailPayload | None = None

    try:
        payload = EmailPayload(email=email)
    except ValueError as err:
        logger.error(f"Email is not a valid email address: {email}: {err}.")
        return

    logger.debug(f"Sending email telemetry event: {email}")

    telemetry_service = get_telemetry_service()

    try:
        await telemetry_service.log_package_email(payload=payload)
    except Exception as err:  # noqa: BLE001
        logger.error(f"Failed to send email telemetry event: {payload.email}: {err}")
        return

    logger.debug(f"Successfully sent email telemetry event: {payload.email}")


@router.get("/")
async def get_registration():
    """Get the registered user (if any)."""
    try:
        registration = await to_thread(load_registration)
        if registration:
            return registration

        return {"message": "No user registered"}  # noqa: TRY300

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load registration: {e!s}") from e
