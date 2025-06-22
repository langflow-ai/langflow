import os
import requests
from fastapi import HTTPException, status
from jose import jwt, jwk
from jose.utils import base64url_decode
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError
from loguru import logger

CLERK_JWKS_URL = "https://capable-squid-34.clerk.accounts.dev/.well-known/jwks.json"

# Cache the JWKs in-memory for better performance
_jwks_cache = None


def get_clerk_secret_key():
    """
    Retrieves Clerk secret key from environment.
    """
    secret = os.environ.get("LANGFLOW_CLERK_SECRET_KEY") or os.environ.get("CLERK_SECRET_KEY")
    logger.debug(f"[CLERK] Loaded secret key: {'set' if secret else 'NOT SET'}")
    return secret


def get_clerk_jwks():
    """
    Downloads Clerk JWKs. Caches them to avoid repeated HTTP calls.
    """
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    try:
        resp = requests.get(CLERK_JWKS_URL)
        resp.raise_for_status()
        _jwks_cache = resp.json()["keys"]
        logger.debug("[CLERK] Successfully loaded Clerk JWKs")
        return _jwks_cache
    except Exception as e:
        logger.error(f"[CLERK] Failed to fetch JWKs: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to fetch Clerk JWKs")


def get_public_key_from_jwt(token: str):
    """
    Extracts the public key from Clerk JWKs using the token's kid header.
    """
    try:
        headers = jwt.get_unverified_header(token)
        kid = headers["kid"]
    except Exception as e:
        logger.error(f"[CLERK] Failed to read JWT header: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT header")

    jwks = get_clerk_jwks()
    key_data = next((k for k in jwks if k["kid"] == kid), None)

    if not key_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Public key not found in Clerk JWKs")

    return jwk.construct(key_data)


def verify_clerk_token(token: str) -> dict:
    try:
        jwks = requests.get(CLERK_JWKS_URL).json()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]

        key_data = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if key_data is None:
            raise HTTPException(status_code=401, detail="Invalid Clerk token: unknown key")

        # Construct the key using python-jose
        public_key = jwk.construct(key_data)

        # Verify the signature
        message, encoded_signature = token.rsplit('.', 1)
        decoded_signature = base64url_decode(encoded_signature.encode())

        if not public_key.verify(message.encode(), decoded_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # If verification passed, decode the claims
        claims = jwt.decode(
            token,
            public_key,
            algorithms=[key_data["alg"]],
            options={"verify_aud": False},  # Set to True if using audience
        )
        return claims

    except (JWTError, ExpiredSignatureError, JWTClaimsError) as e:
        raise HTTPException(status_code=401, detail="Invalid Clerk token") from e


def get_clerk_user_id(claims: dict) -> str:
    """
    Returns the Clerk user ID from the claims (usually in 'sub').
    """
    return claims.get("sub")


def get_clerk_user_email(claims: dict) -> str:
    """
    Returns the user's email, preferring the first in `email_addresses` if available.
    """
    emails = claims.get("email_addresses", [])
    if emails and isinstance(emails, list):
        return emails[0].get("email_address")
    return claims.get("email")


def get_clerk_username(claims: dict) -> str:
    """
    Extracts a username from Clerk claims, preferring 'username', then email prefix, then 'sub'.
    """
    if "username" in claims and claims["username"]:
        return claims["username"]

    email = claims.get("email") or (
        claims.get("email_addresses", [{}])[0].get("email_address")
        if claims.get("email_addresses") else None
    )

    if email:
        return email.split("@")[0]

    return claims.get("sub")
