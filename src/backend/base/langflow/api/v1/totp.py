"""TOTP (Two-Factor Authentication) API endpoints.

Provides per-user TOTP setup, enable/disable, and login verification.
Compatible with Google Authenticator, Authy, and all RFC 6238 TOTP clients.
"""

from __future__ import annotations

import re
from uuid import UUID

import jwt
from fastapi import APIRouter, HTTPException, Response, status
from jwt import InvalidTokenError
from pydantic import BaseModel, field_validator

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.login import _issue_full_tokens
from langflow.services.auth.totp import (
    burn_partial_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_totp_secret,
    get_provisioning_uri,
    is_partial_token_burnt,
    is_replay,
    is_valid_base32,
    mark_used,
    record_partial_token_failure,
    verify_totp_code,
)
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.deps import get_auth_service, get_settings_service

router = APIRouter(tags=["TOTP"])

PARTIAL_TOKEN_TYPE = "partial"  # noqa: S105
_SIX_DIGIT_RE = re.compile(r"^\d{6}$")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class TOTPSetupResponse(BaseModel):
    provisioning_uri: str
    raw_secret: str


class TOTPStatusResponse(BaseModel):
    totp_enabled: bool


class TOTPEnableRequest(BaseModel):
    code: str
    raw_secret: str

    @field_validator("code")
    @classmethod
    def code_must_be_six_digits(cls, v: str) -> str:
        if not _SIX_DIGIT_RE.match(v):
            msg = "TOTP code must be exactly 6 digits."
            raise ValueError(msg)
        return v

    @field_validator("raw_secret")
    @classmethod
    def secret_must_be_base32(cls, v: str) -> str:
        if not is_valid_base32(v):
            msg = "Invalid TOTP secret format."
            raise ValueError(msg)
        return v.upper()


class TOTPDisableRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def code_must_be_six_digits(cls, v: str) -> str:
        if not _SIX_DIGIT_RE.match(v):
            msg = "TOTP code must be exactly 6 digits."
            raise ValueError(msg)
        return v


class TOTPVerifyLoginRequest(BaseModel):
    partial_token: str
    code: str

    @field_validator("code")
    @classmethod
    def code_must_be_six_digits(cls, v: str) -> str:
        if not _SIX_DIGIT_RE.match(v):
            msg = "TOTP code must be exactly 6 digits."
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=TOTPStatusResponse)
async def get_totp_status(current_user: CurrentActiveUser) -> TOTPStatusResponse:
    """Return whether TOTP is currently enabled for the authenticated user."""
    return TOTPStatusResponse(totp_enabled=bool(current_user.totp_enabled))


@router.post("/setup", response_model=TOTPSetupResponse)
async def setup_totp(current_user: CurrentActiveUser) -> TOTPSetupResponse:
    """Generate a fresh TOTP secret and provisioning URI.

    Does NOT enable TOTP yet — the user must verify a code with /totp/enable first.
    The returned raw_secret is only used client-side to call /totp/enable and is
    never persisted until that call succeeds.
    """
    raw_secret = generate_totp_secret()
    provisioning_uri = get_provisioning_uri(raw_secret, current_user.username)
    return TOTPSetupResponse(provisioning_uri=provisioning_uri, raw_secret=raw_secret)


@router.post("/enable", response_model=TOTPStatusResponse)
async def enable_totp(
    body: TOTPEnableRequest,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> TOTPStatusResponse:
    """Verify the TOTP code for the given secret and, on success, save + enable TOTP.

    The client must pass the raw_secret returned by /totp/setup together with
    the 6-digit code from their authenticator app.
    """
    user_id_str = str(current_user.id)
    if is_replay(user_id_str, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP code already used. Wait for the next code.",
        )

    if not verify_totp_code(body.raw_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code. Make sure your authenticator app is synced.",
        )

    mark_used(user_id_str, body.code)

    encrypted_secret = encrypt_totp_secret(body.raw_secret)
    current_user.totp_secret = encrypted_secret
    current_user.totp_enabled = True
    db.add(current_user)
    await db.commit()

    return TOTPStatusResponse(totp_enabled=True)


@router.post("/disable", response_model=TOTPStatusResponse)
async def disable_totp(
    body: TOTPDisableRequest,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> TOTPStatusResponse:
    """Disable TOTP for the authenticated user after verifying the current code.

    Requires a valid TOTP code (not just the password) to prevent account takeover.
    """
    if not current_user.totp_enabled or not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is not enabled for this account.",
        )

    user_id_str = str(current_user.id)
    if is_replay(user_id_str, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP code already used. Wait for the next code.",
        )

    raw_secret = decrypt_totp_secret(current_user.totp_secret)
    if not raw_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify TOTP. Please contact an administrator.",
        )

    if not verify_totp_code(raw_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code.",
        )

    mark_used(user_id_str, body.code)

    current_user.totp_secret = None
    current_user.totp_enabled = False
    db.add(current_user)
    await db.commit()

    return TOTPStatusResponse(totp_enabled=False)


@router.post("/verify-login", response_model=None)
async def verify_totp_login(
    body: TOTPVerifyLoginRequest,
    response: Response,
    db: DbSession,
):
    """Complete login for a user who has TOTP enabled.

    Validates the short-lived partial_token issued by POST /login, verifies the
    TOTP code, and on success issues full access + refresh tokens (identical to a
    normal login response).

    Security:
    * The partial_token is burned after a successful verification (single-use).
    * After MAX_VERIFY_ATTEMPTS consecutive failures the partial_token is also
      burned, preventing brute-force enumeration of the 6-digit code.
    * Per-code replay prevention is applied even after the first success.
    """
    auth = get_auth_service()
    auth_settings = get_settings_service().auth_settings

    # ------------------------------------------------------------------
    # 1. Reject already-used / exhausted partial tokens immediately
    #    (before any expensive DB or crypto work).
    # ------------------------------------------------------------------
    if is_partial_token_burnt(body.partial_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or already used. Please log in again.",
        )

    from langflow.services.auth.utils import get_jwt_verification_key

    verification_key = get_jwt_verification_key(get_settings_service())

    try:
        payload = jwt.decode(
            body.partial_token,
            verification_key,
            algorithms=[auth_settings.ALGORITHM],
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
        ) from exc

    token_type: str = payload.get("type", "")
    if token_type != PARTIAL_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token.",
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token.",
        ) from exc

    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is not enabled for this account.",
        )

    # ------------------------------------------------------------------
    # 2. Per-code replay check.
    # ------------------------------------------------------------------
    user_id_str = str(user.id)
    if is_replay(user_id_str, body.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOTP code already used. Wait for the next code.",
        )

    # ------------------------------------------------------------------
    # 3. Decrypt secret — a failure here means the SECRET_KEY was rotated
    #    or the stored value is corrupt, not a user error.
    # ------------------------------------------------------------------
    raw_secret = decrypt_totp_secret(user.totp_secret)
    if not raw_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify TOTP. Please contact an administrator.",
        )

    # ------------------------------------------------------------------
    # 4. Verify the code; track failures, burn on success.
    # ------------------------------------------------------------------
    if not verify_totp_code(raw_secret, body.code):
        remaining = record_partial_token_failure(body.partial_token)
        from langflow.services.auth.totp import MAX_VERIFY_ATTEMPTS

        attempts_left = MAX_VERIFY_ATTEMPTS - remaining
        if attempts_left <= 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Too many failed attempts. Please log in again.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code.",
        )

    mark_used(user_id_str, body.code)
    burn_partial_token(body.partial_token)  # single-use: no re-login with same token

    return await _issue_full_tokens(response, auth, auth_settings, user, db)
