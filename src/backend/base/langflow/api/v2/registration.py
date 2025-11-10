import json
from asyncio import to_thread
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from langflow.logging import logger

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
            return RegisterResponse(email=email)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e!s}") from e


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
