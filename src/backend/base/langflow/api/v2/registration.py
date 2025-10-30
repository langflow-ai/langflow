import json
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
    success: bool
    message: str
    email: str


# File to store registrations
REGISTRATION_FILE = Path("data/user/registration.json")

try:
    # Ensure the directory exists with secure permissions
    REGISTRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Set directory permissions to owner read/write/execute only (if possible)
    REGISTRATION_FILE.parent.chmod(0o700)
except Exception as e:
    logger.error(f"Failed to create registration directory: {e}")
    raise

# Optionally, set file permissions to owner read/write only when file is created
if not REGISTRATION_FILE.exists():
    try:
        REGISTRATION_FILE.touch(exist_ok=True)
        REGISTRATION_FILE.chmod(0o600)
    except Exception as e:
        logger.error(f"Failed to create registration file: {e}")
        raise

# TODO: Move functions to a separate service module


def load_registration() -> dict | None:
    """Load the single registration from file."""
    if REGISTRATION_FILE.exists():
        try:
            with REGISTRATION_FILE.open("r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Corrupted registration file: {REGISTRATION_FILE}")
            return None
    return None


def save_registration(email: str) -> bool:
    """Save the single registration to file.

    Args:
        email: Email to register

    Returns:
        True if saved successfully
    """
    try:
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

        # Save to local file (replace existing)
        if save_registration(email):
            return RegisterResponse(success=True, message="Registration successful", email=email)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e!s}") from e


@router.get("/")
async def get_registration():
    """Get the registered user (if any)."""
    try:
        registration = load_registration()
        if registration:
            return registration

        return {"message": "No user registered"}  # noqa: TRY300

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load registration: {e!s}") from e
