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
REGISTRATIONS_FILE = Path("data/users/registrations.json")
REGISTRATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

# TODO: Move functions to a separate service module


def load_registrations() -> list[dict]:
    """Load existing registrations from file."""
    if REGISTRATIONS_FILE.exists():
        with REGISTRATIONS_FILE.open("r") as f:
            return json.load(f)
    return []


def save_registration(email: str) -> bool:
    return _save_registration(email=email, append=False)


def append_registration(email: str) -> bool:
    return _save_registration(email=email, append=True)


def _save_registration(email: str, append: bool) -> bool:  # noqa: FBT001
    """Save a new registration to file with atomic write."""
    try:
        registrations = load_registrations()

        # Check if email already exists
        if any(reg["email"] == email for reg in registrations):
            return False

        # Add new registration
        registration = {
            "email": email,
            "registered_at": datetime.now(tz=timezone.utc).isoformat(),
            "langflow_connected": False,
        }

        if append:
            registrations.append(registration)
        else:
            registrations = [registration]

        # Save to file
        temp_file = REGISTRATIONS_FILE.with_suffix(".tmp")
        with temp_file.open("w") as f:
            json.dump(registrations, f, indent=2)
        temp_file.replace(REGISTRATIONS_FILE)

    except Exception as e:
        logger.error(f"Error saving registration: {e}")
        raise
    else:
        return True


@router.post("/", response_model=RegisterResponse)
async def register_user(request: RegisterRequest):
    """Register a new user with their email."""
    try:
        email = request.email

        # Save to local file
        if save_registration(email):
            return RegisterResponse(success=True, message="Registration successful", email=email)

        raise HTTPException(status_code=400, detail="Email already registered")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e!s}") from e


@router.get("/")
async def get_registrations():
    """Get all registered users."""
    try:
        registrations = load_registrations()
        return {"total": len(registrations), "registrations": registrations}
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to load registrations: {e!r}") from e


@router.get("/info")
async def root():
    """Root endpoint."""
    return {
        "service": "Langflow Desktop Registration API",
        "endpoints": [{"path": "/", "method": "POST"}, {"path": "/", "method": "GET"}],
    }
