"""Mock OIDC server for testing the Keycloak SSO plugin.

Simulates Keycloak's client-level access control with 10 employees:
  - Some have access to all projects (all Langflow instances)
  - Some have access to only one project
  - Some have no access at all

Each Langflow instance uses a different KEYCLOAK_CLIENT_ID to represent its project.
Keycloak enforces authorization at the client level — only users assigned to a
client can obtain a token for it. This mock replicates that behaviour.

Usage:
    python scripts/mock_oidc_server.py

Langflow instance for project-a:
    KEYCLOAK_ENABLED=true
    KEYCLOAK_SERVER_URL=http://localhost:9000
    KEYCLOAK_REALM=company
    KEYCLOAK_CLIENT_ID=langflow-project-a
    KEYCLOAK_CLIENT_SECRET=mock-secret
    KEYCLOAK_SHARED_USERNAME=project-a-shared
    KEYCLOAK_REDIRECT_URI=http://localhost:7860/api/v1/keycloak/callback

Langflow instance for project-b:
    KEYCLOAK_CLIENT_ID=langflow-project-b
    KEYCLOAK_SHARED_USERNAME=project-b-shared
    KEYCLOAK_REDIRECT_URI=http://localhost:7861/api/v1/keycloak/callback
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
# Config
# ---------------------------------------------------------------------------

PORT = 9000
BASE_URL = f"http://localhost:{PORT}"
REALM = "company"

# ---------------------------------------------------------------------------
# 10 employees — username = 사번 (EMP001~EMP010)
#
# projects: which Langflow client_ids this employee can access
#   - "all"       → access to every client (superuser / platform admin)
#   - ["project-a"] → access only to langflow-project-a
#   - []          → no Langflow access at all
# ---------------------------------------------------------------------------

EMPLOYEES: dict[str, dict] = {
    # ── 모든 프로젝트 접근 가능 (2명) ──────────────────────────────────────
    "EMP001": {"password": "pass001", "name": "김철수", "projects": "all"},
    "EMP002": {"password": "pass002", "name": "이영희", "projects": "all"},
    # ── project-a 전용 (3명) ──────────────────────────────────────────────
    "EMP003": {"password": "pass003", "name": "박민준", "projects": ["project-a"]},
    "EMP004": {"password": "pass004", "name": "최지은", "projects": ["project-a"]},
    "EMP005": {"password": "pass005", "name": "정우진", "projects": ["project-a"]},
    # ── project-b 전용 (3명) ──────────────────────────────────────────────
    "EMP006": {"password": "pass006", "name": "강수현", "projects": ["project-b"]},
    "EMP007": {"password": "pass007", "name": "윤서연", "projects": ["project-b"]},
    "EMP008": {"password": "pass008", "name": "임도현", "projects": ["project-b"]},
    # ── 접근 권한 없음 (2명) ─────────────────────────────────────────────
    "EMP009": {"password": "pass009", "name": "한지우", "projects": []},
    "EMP010": {"password": "pass010", "name": "오세훈", "projects": []},
}


def _has_access(employee: dict, client_id: str) -> bool:
    """Return True if this employee can authenticate against the given client."""
    projects = employee["projects"]
    if projects == "all":
        return True
    # client_id convention: "langflow-{project-name}"
    project = client_id.removeprefix("langflow-")
    return project in projects


# ---------------------------------------------------------------------------
# RSA key pair (generated once at startup)
# ---------------------------------------------------------------------------

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()
_private_pem = _private_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption(),
)

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
# In-memory auth code store  { code -> (employee_id, client_id) }
# ---------------------------------------------------------------------------

_codes: dict[str, tuple[str, str]] = {}

# ---------------------------------------------------------------------------
# JWT helper
# ---------------------------------------------------------------------------


def _issue_token(employee_id: str, client_id: str) -> str:
    import jwt

    emp = EMPLOYEES[employee_id]
    now = int(time.time())
    payload = {
        "iss": f"{BASE_URL}/realms/{REALM}",
        "sub": employee_id,
        "aud": client_id,
        "iat": now,
        "exp": now + 3600,
        "preferred_username": employee_id,
        "name": emp["name"],
        "email": f"{employee_id.lower()}@company.com",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _private_pem, algorithm="RS256", headers={"kid": _KID})


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

REALM_BASE = f"/realms/{REALM}/protocol/openid-connect"


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    print(f"""
╭──────────────────────────────────────────────────────────────────╮
│  Mock Keycloak running at {BASE_URL}  (realm: {REALM})
│
│  Langflow project-a 인스턴스 환경변수:
│    KEYCLOAK_CLIENT_ID=langflow-project-a
│    KEYCLOAK_SHARED_USERNAME=project-a-shared
│
│  Langflow project-b 인스턴스 환경변수:
│    KEYCLOAK_CLIENT_ID=langflow-project-b
│    KEYCLOAK_SHARED_USERNAME=project-b-shared
│
│  Admin 페이지: {BASE_URL}/admin
╰──────────────────────────────────────────────────────────────────╯
""")
    yield


app = FastAPI(title="Mock Keycloak", docs_url=None, redoc_url=None, lifespan=_lifespan)


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
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "claims_supported": ["sub", "iss", "email", "preferred_username", "name"],
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
    """Show login form. client_id determines which project is being accessed."""
    project = client_id.removeprefix("langflow-")
    state_input = f'<input type="hidden" name="state" value="{state}">'
    redirect_input = f'<input type="hidden" name="redirect_uri" value="{urllib.parse.quote(redirect_uri)}">'
    client_input = f'<input type="hidden" name="client_id" value="{client_id}">'

    html = f"""
    <html><head><title>Mock Keycloak — {project}</title>
    <style>
      body {{ font-family: sans-serif; display:flex; justify-content:center; padding-top:80px; background:#f0f4f8; }}
      .box {{ background:#fff; padding:32px; border-radius:8px; box-shadow:0 2px 12px rgba(0,0,0,.12); width:380px; }}
      h2 {{ margin-top:0; color:#333; }} .project {{ color:#4a90d9; font-weight:bold; }}
      input[type=text],input[type=password] {{ width:100%; padding:8px; margin:6px 0 14px;
        box-sizing:border-box; border:1px solid #ccc; border-radius:4px; }}
      button {{ width:100%; padding:10px; background:#4a90d9; color:#fff; border:none;
        border-radius:4px; cursor:pointer; font-size:15px; }}
      button:hover {{ background:#357abd; }}
      .hint {{ margin-top:16px; font-size:12px; color:#888; }}
      a {{ color:#4a90d9; text-decoration:none; }}
    </style></head>
    <body><div class="box">
      <h2>🔑 Mock Keycloak<br><span class="project">{project}</span></h2>
      <form method="POST" action="{REALM_BASE}/auth/submit">
        {state_input}{redirect_input}{client_input}
        <label>사번 (Username)</label>
        <input type="text" name="username" placeholder="예: EMP001" autofocus required>
        <label>Password</label>
        <input type="password" name="password" required>
        <button type="submit">로그인</button>
      </form>
      <p class="hint">접근 권한이 없으면 로그인이 거부됩니다. <a href="/admin" target="_blank">계정 목록 보기 →</a></p>
    </div></body></html>
    """
    return HTMLResponse(html)


@app.post(f"{REALM_BASE}/auth/submit")
async def authorization_submit(
    username: str = Form(...),
    password: str = Form(...),
    client_id: str = Form(...),
    state: str = Form(""),
    redirect_uri: str = Form(...),
):
    redirect_uri = urllib.parse.unquote(redirect_uri)
    emp = EMPLOYEES.get(username.upper())

    # 1. 사번/비밀번호 확인
    if not emp or emp["password"] != password:
        return HTMLResponse(_error_page("사번 또는 비밀번호가 올바르지 않습니다."), status_code=401)

    # 2. 클라이언트(프로젝트) 접근 권한 확인 — 실제 Keycloak의 client-level access control
    if not _has_access(emp, client_id):
        project = client_id.removeprefix("langflow-")
        return HTMLResponse(
            _error_page(f"'{emp['name']} ({username})' 계정은 <b>{project}</b> 프로젝트에 접근 권한이 없습니다."),
            status_code=403,
        )

    # 3. 인증 코드 발급
    code = str(uuid.uuid4())
    _codes[code] = (username.upper(), client_id)
    params = {"code": code, **({"state": state} if state else {})}
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
    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    entry = _codes.pop(code, None)
    if not entry:
        return JSONResponse({"error": "invalid_grant", "error_description": "Code not found or already used"}, status_code=400)

    employee_id, issued_client_id = entry
    access_token = _issue_token(employee_id, issued_client_id)
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "openid email profile",
    }


@app.get("/admin", include_in_schema=False)
async def admin_page():
    """Read-only page showing all employees and their project access."""
    def _badge(projects) -> str:
        if projects == "all":
            return '<span class="all">모든 프로젝트</span>'
        if not projects:
            return '<span class="none">접근 권한 없음</span>'
        return "".join(f'<span class="tag">{p}</span>' for p in projects)

    rows = "".join(
        f"<tr><td><code>{eid}</code></td><td>{e['name']}</td>"
        f"<td><code>{e['password']}</code></td><td>{_badge(e['projects'])}</td></tr>"
        for eid, e in EMPLOYEES.items()
    )
    html = f"""
    <html><head><title>Mock Keycloak Admin</title>
    <style>
      body {{ font-family: sans-serif; padding:40px; background:#f0f4f8; }}
      h1 {{ color:#333; margin-bottom:4px; }} .sub {{ color:#888; font-size:13px; margin-bottom:24px; }}
      table {{ border-collapse:collapse; background:#fff; border-radius:8px;
               box-shadow:0 2px 8px rgba(0,0,0,.1); width:100%; max-width:780px; }}
      th {{ background:#4a90d9; color:#fff; padding:12px 16px; text-align:left; }}
      td {{ padding:10px 16px; border-bottom:1px solid #eee; vertical-align:middle; }}
      tr:last-child td {{ border-bottom:none; }}
      .tag {{ display:inline-block; background:#e8f0fe; color:#1a56db;
              border-radius:12px; padding:2px 10px; font-size:12px; margin:2px; }}
      .all {{ display:inline-block; background:#d1fae5; color:#065f46;
              border-radius:12px; padding:2px 10px; font-size:12px; }}
      .none {{ display:inline-block; background:#fee2e2; color:#991b1b;
               border-radius:12px; padding:2px 10px; font-size:12px; }}
      code {{ background:#f0f0f0; padding:2px 6px; border-radius:4px; font-size:13px; }}
    </style></head>
    <body>
      <h1>🔑 Mock Keycloak Admin</h1>
      <p class="sub">Realm: <b>{REALM}</b> &nbsp;|&nbsp; {BASE_URL}</p>
      <table>
        <thead><tr><th>사번</th><th>이름</th><th>Password</th><th>접근 가능 프로젝트</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </body></html>
    """
    return HTMLResponse(html)


def _error_page(message: str) -> str:
    return f"""
    <html><head><title>접근 거부</title>
    <style>
      body {{ font-family:sans-serif; display:flex; justify-content:center; padding-top:80px; background:#f0f4f8; }}
      .box {{ background:#fff; padding:32px; border-radius:8px; box-shadow:0 2px 12px rgba(0,0,0,.12);
              width:380px; text-align:center; }}
      h3 {{ color:#dc2626; }} p {{ color:#555; }} a {{ color:#4a90d9; }}
    </style></head>
    <body><div class="box">
      <h3>❌ 로그인 실패</h3>
      <p>{message}</p>
      <p><a href="javascript:history.back()">← 돌아가기</a></p>
    </div></body></html>
    """


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
