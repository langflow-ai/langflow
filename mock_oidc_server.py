"""Mock OIDC server for testing the Keycloak SSO plugin.

Simulates the Keycloak OIDC endpoints:
  GET  /.well-known/openid-configuration   — discovery
  GET  /realms/test/protocol/openid-connect/auth    — authorization (auto-redirects)
  POST /realms/test/protocol/openid-connect/token   — token exchange
  GET  /realms/test/protocol/openid-connect/certs   — JWKS

Usage:
    python mock_oidc_server.py

Configure groups per user in MOCK_USERS below, then set env vars and run Langflow:
    KEYCLOAK_ENABLED=true
    KEYCLOAK_SERVER_URL=http://localhost:9000
    KEYCLOAK_REALM=test
    KEYCLOAK_CLIENT_ID=langflow
    KEYCLOAK_CLIENT_SECRET=mock-secret
    KEYCLOAK_REDIRECT_URI=http://localhost:7860/api/v1/keycloak/callback
"""

import base64
import contextlib
import time
import urllib.parse
import uuid

import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# ---------------------------------------------------------------------------
# Config — edit these to match your test scenario
# ---------------------------------------------------------------------------

PORT = 9000
BASE_URL = f"http://localhost:{PORT}"
REALM = "test"
CLIENT_ID = "langflow"
CLIENT_SECRET = "mock-secret"

# username → { password, groups }
MOCK_USERS = {
    "alice": {"password": "alice123", "groups": ["/project-a"]},
    "bob":   {"password": "bob123",   "groups": ["/project-a"]},
    "carol": {"password": "carol123", "groups": ["/project-b"]},
    "admin": {"password": "admin",    "groups": ["/project-a", "/project-b"]},
}

# ---------------------------------------------------------------------------
# RSA key pair (generated once at startup — used to sign JWTs)
# ---------------------------------------------------------------------------

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()

_private_pem = _private_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption(),
)

# Build JWKS from the public key
_pub_numbers = _public_key.public_numbers()
_KID = "mock-key-1"

def _b64url(n: int) -> str:
    length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()

JWKS = {
    "keys": [
        {
            "kty": "RSA",
            "use": "sig",
            "kid": _KID,
            "alg": "RS256",
            "n": _b64url(_pub_numbers.n),
            "e": _b64url(_pub_numbers.e),
        }
    ]
}

# ---------------------------------------------------------------------------
# In-memory auth code store  { code -> username }
# ---------------------------------------------------------------------------

_codes: dict[str, str] = {}

# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _issue_token(username: str, groups: list[str]) -> str:
    import jwt

    now = int(time.time())
    payload = {
        "iss": f"{BASE_URL}/realms/{REALM}",
        "sub": username,
        "aud": CLIENT_ID,
        "iat": now,
        "exp": now + 3600,
        "preferred_username": username,
        "email": f"{username}@mock.local",
        "groups": groups,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _private_pem, algorithm="RS256", headers={"kid": _KID})

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    print(f"""
╭─────────────────────────────────────────────────────╮
│  Mock OIDC Server running on {BASE_URL}
│
│  Set these env vars before starting Langflow:
│
│  KEYCLOAK_ENABLED=true
│  KEYCLOAK_SERVER_URL={BASE_URL}
│  KEYCLOAK_REALM={REALM}
│  KEYCLOAK_CLIENT_ID={CLIENT_ID}
│  KEYCLOAK_CLIENT_SECRET={CLIENT_SECRET}
│  KEYCLOAK_REDIRECT_URI=http://localhost:7860/api/v1/keycloak/callback
╰─────────────────────────────────────────────────────╯
""")
    yield


app = FastAPI(title="Mock OIDC Server", docs_url=None, redoc_url=None, lifespan=_lifespan)

REALM_BASE = f"/realms/{REALM}/protocol/openid-connect"


@app.get("/.well-known/openid-configuration")
@app.get(f"/realms/{REALM}/.well-known/openid-configuration")
async def discovery():
    return {
        "issuer": f"{BASE_URL}/realms/{REALM}",
        "authorization_endpoint": f"{BASE_URL}{REALM_BASE}/auth",
        "token_endpoint": f"{BASE_URL}{REALM_BASE}/token",
        "jwks_uri": f"{BASE_URL}{REALM_BASE}/certs",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "email", "profile"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        "claims_supported": ["sub", "iss", "email", "preferred_username", "groups"],
    }


@app.get(f"{REALM_BASE}/certs")
async def jwks():
    return JWKS


@app.get(f"{REALM_BASE}/auth")
async def authorization(
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    scope: str = "openid",
    state: str = "",
):
    """Show a minimal login form."""
    state_input = f'<input type="hidden" name="state" value="{state}">'
    redirect_input = f'<input type="hidden" name="redirect_uri" value="{urllib.parse.quote(redirect_uri)}">'
    user_list = "".join(
        f"<li><b>{u}</b> / {d['password']} → groups: {d['groups']}</li>"
        for u, d in MOCK_USERS.items()
    )
    html = f"""
    <html><head><title>Mock Keycloak Login</title>
    <style>
      body {{ font-family: sans-serif; display:flex; justify-content:center; padding-top:80px; background:#f5f5f5; }}
      .box {{ background:#fff; padding:32px; border-radius:8px; box-shadow:0 2px 12px rgba(0,0,0,.15); width:360px; }}
      h2 {{ margin-top:0; color:#333; }}
      input[type=text],input[type=password] {{ width:100%; padding:8px; margin:6px 0 14px; box-sizing:border-box; border:1px solid #ccc; border-radius:4px; }}
      button {{ width:100%; padding:10px; background:#4a90d9; color:#fff; border:none; border-radius:4px; cursor:pointer; font-size:15px; }}
      button:hover {{ background:#357abd; }}
      .users {{ margin-top:20px; font-size:12px; color:#666; background:#f9f9f9; padding:10px; border-radius:4px; }}
    </style></head>
    <body><div class="box">
      <h2>🔑 Mock Keycloak</h2>
      <form method="POST" action="{REALM_BASE}/auth/submit">
        {state_input}
        {redirect_input}
        <label>Username</label>
        <input type="text" name="username" autofocus required>
        <label>Password</label>
        <input type="password" name="password" required>
        <button type="submit">Sign In</button>
      </form>
      <div class="users"><b>Test accounts:</b><ul>{user_list}</ul></div>
    </div></body></html>
    """
    return HTMLResponse(html)


@app.post(f"{REALM_BASE}/auth/submit")
async def authorization_submit(
    username: str = Form(...),
    password: str = Form(...),
    state: str = Form(""),
    redirect_uri: str = Form(...),
):
    """Validate credentials and redirect back with auth code."""
    redirect_uri = urllib.parse.unquote(redirect_uri)
    user = MOCK_USERS.get(username)

    if not user or user["password"] != password:
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;padding:40px'>"
            "<h3 style='color:red'>❌ Invalid username or password</h3>"
            "<a href='javascript:history.back()'>← Back</a></body></html>",
            status_code=401,
        )

    code = str(uuid.uuid4())
    _codes[code] = username

    params = {"code": code}
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=redirect_uri + sep + urllib.parse.urlencode(params), status_code=302)


@app.post(f"{REALM_BASE}/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(default=""),
    redirect_uri: str = Form(default=""),
    client_id: str = Form(default=""),
    client_secret: str = Form(default=""),
):
    """Exchange authorization code for tokens."""
    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    username = _codes.pop(code, None)
    if not username:
        return JSONResponse({"error": "invalid_grant", "error_description": "Code not found or already used"}, status_code=400)

    user = MOCK_USERS[username]
    access_token = _issue_token(username, user["groups"])

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "openid email profile",
    }




if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
