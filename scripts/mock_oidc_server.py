# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastapi>=0.111",
#   "uvicorn[standard]>=0.29",
#   "cryptography>=42",
#   "python-multipart>=0.0.9",
#   "pyjwt>=2.8",
# ]
# ///

"""Mock OIDC server for testing the Keycloak SSO plugin.

Simulates Keycloak's group-based client access control:

  Groups
  ├── langflow-admins     → 모든 Langflow 인스턴스 접근 가능
  ├── project-a-members   → langflow-project-a 만 접근 가능
  └── project-b-members   → langflow-project-b 만 접근 가능

  Employees without any group → 접근 불가

Usage:
    uv run scripts/mock_oidc_server.py

Then start Langflow instances:
    bash scripts/start_dev.sh
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
# 10 employees (사번 EMP001~EMP010)
# ---------------------------------------------------------------------------

EMPLOYEES: dict[str, dict] = {
    "EMP001": {"password": "pass001", "name": "김철수"},
    "EMP002": {"password": "pass002", "name": "이영희"},
    "EMP003": {"password": "pass003", "name": "박민준"},
    "EMP004": {"password": "pass004", "name": "최지은"},
    "EMP005": {"password": "pass005", "name": "정우진"},
    "EMP006": {"password": "pass006", "name": "강수현"},
    "EMP007": {"password": "pass007", "name": "윤서연"},
    "EMP008": {"password": "pass008", "name": "임도현"},
    "EMP009": {"password": "pass009", "name": "한지우"},
    "EMP010": {"password": "pass010", "name": "오세훈"},
}

# ---------------------------------------------------------------------------
# Groups — mirrors Keycloak group / client-scope assignment
#
# clients: "all"            → 모든 Langflow 클라이언트 접근 허용 (전사 관리자)
#          ["client-id",…]  → 지정된 클라이언트만 허용
# ---------------------------------------------------------------------------

GROUPS: dict[str, dict] = {
    "langflow-admins": {
        "label": "전사 관리자",
        "members": ["EMP001", "EMP002"],
        "clients": "all",
    },
    "project-a-members": {
        "label": "Project-A 멤버",
        "members": ["EMP003", "EMP004", "EMP005"],
        "clients": ["langflow-project-a"],
    },
    "project-b-members": {
        "label": "Project-B 멤버",
        "members": ["EMP006", "EMP007", "EMP008"],
        "clients": ["langflow-project-b"],
    },
    # EMP009, EMP010 은 어느 그룹에도 속하지 않음 → 접근 불가
}


def _get_employee_groups(employee_id: str) -> list[str]:
    return [name for name, g in GROUPS.items() if employee_id in g["members"]]


def _has_client_access(employee_id: str, client_id: str) -> bool:
    """Return True if the employee has access to the given Keycloak client."""
    for group_name in _get_employee_groups(employee_id):
        clients = GROUPS[group_name]["clients"]
        if clients == "all" or client_id in clients:
            return True
    return False


# ---------------------------------------------------------------------------
# RSA key pair
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

# In-memory auth code store: code → (employee_id, client_id)
_codes: dict[str, tuple[str, str]] = {}


def _issue_token(employee_id: str, client_id: str) -> str:
    import jwt

    emp = EMPLOYEES[employee_id]
    now = int(time.time())
    return jwt.encode(
        {
            "iss": f"{BASE_URL}/realms/{REALM}",
            "sub": employee_id,
            "aud": client_id,
            "iat": now,
            "exp": now + 3600,
            "preferred_username": employee_id,
            "name": emp["name"],
            "email": f"{employee_id.lower()}@company.com",
            "jti": str(uuid.uuid4()),
        },
        _private_pem,
        algorithm="RS256",
        headers={"kid": _KID},
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

REALM_BASE = f"/realms/{REALM}/protocol/openid-connect"


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    print(f"""
╭──────────────────────────────────────────────────────────────────╮
│  Mock Keycloak  {BASE_URL}  (realm: {REALM})
│  Admin 페이지:  {BASE_URL}/admin
│
│  Langflow 인스턴스 실행: bash scripts/start_dev.sh
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
    project = client_id.removeprefix("langflow-")
    state_input = f'<input type="hidden" name="state" value="{state}">'
    redirect_input = f'<input type="hidden" name="redirect_uri" value="{urllib.parse.quote(redirect_uri)}">'
    client_input = f'<input type="hidden" name="client_id" value="{client_id}">'

    html = f"""
    <html><head><title>Mock Keycloak — {project}</title>
    <style>
      body {{ font-family: sans-serif; display:flex; justify-content:center;
              padding-top:80px; background:#f0f4f8; }}
      .box {{ background:#fff; padding:32px; border-radius:8px;
              box-shadow:0 2px 12px rgba(0,0,0,.12); width:380px; }}
      h2 {{ margin-top:0; color:#333; }}
      .project {{ color:#4a90d9; font-weight:bold; }}
      input[type=text], input[type=password] {{
        width:100%; padding:8px; margin:6px 0 14px;
        box-sizing:border-box; border:1px solid #ccc; border-radius:4px; }}
      button {{ width:100%; padding:10px; background:#4a90d9; color:#fff;
                border:none; border-radius:4px; cursor:pointer; font-size:15px; }}
      button:hover {{ background:#357abd; }}
      .hint {{ margin-top:16px; font-size:12px; color:#888; }}
      a {{ color:#4a90d9; text-decoration:none; }}
    </style></head>
    <body><div class="box">
      <h2>🔑 Mock Keycloak<br><span class="project">{project}</span></h2>
      <form method="POST" action="{REALM_BASE}/auth/submit">
        {state_input}{redirect_input}{client_input}
        <label>사번</label>
        <input type="text" name="username" placeholder="예: EMP001" autofocus required>
        <label>Password</label>
        <input type="password" name="password" required>
        <button type="submit">로그인</button>
      </form>
      <p class="hint">
        접근 권한이 없으면 로그인이 거부됩니다.
        <a href="/admin" target="_blank">계정 목록 →</a>
      </p>
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
    emp_id = username.upper()
    emp = EMPLOYEES.get(emp_id)

    if not emp or emp["password"] != password:
        return HTMLResponse(_error_page("사번 또는 비밀번호가 올바르지 않습니다."), status_code=401)

    if not _has_client_access(emp_id, client_id):
        project = client_id.removeprefix("langflow-")
        groups = _get_employee_groups(emp_id)
        reason = "소속 그룹 없음" if not groups else f"소속 그룹: {', '.join(groups)}"
        return HTMLResponse(
            _error_page(
                f"<b>{emp['name']} ({emp_id})</b> 계정은 "
                f"<b>{project}</b> 프로젝트에 접근 권한이 없습니다.<br>"
                f"<small style='color:#999'>({reason})</small>"
            ),
            status_code=403,
        )

    code = str(uuid.uuid4())
    _codes[code] = (emp_id, client_id)
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
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Code not found or already used"}, status_code=400
        )

    employee_id, issued_client_id = entry
    return {
        "access_token": _issue_token(employee_id, issued_client_id),
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "openid email profile",
    }


# ---------------------------------------------------------------------------
# Mock HCP roles API — mirrors http://hcp-api.com/v1/projects/{project}/roles
# ---------------------------------------------------------------------------

# Project → allowed employees mapping (simulates HCP API per-project roles)
HCP_PROJECT_ROLES: dict[str, dict] = {
    "project-a": {
        "managers": ["EMP001"],
        "deployApprovers": ["EMP002"],
        "developers": ["EMP003", "EMP004", "EMP005"],
    },
    "project-b": {
        "managers": ["EMP001"],
        "deployApprovers": ["EMP002"],
        "developers": ["EMP006", "EMP007", "EMP008"],
    },
}


@app.get("/v1/projects/{project_name}/roles")
async def hcp_roles(project_name: str):
    """Mock HCP roles API endpoint."""
    roles = HCP_PROJECT_ROLES.get(project_name, {"managers": [], "deployApprovers": [], "developers": []})
    return {"response": roles}


@app.get("/admin", include_in_schema=False)
async def admin_page():
    """Read-only page: employees, groups, and client access."""
    # ── Group table ───────────────────────────────────────────────────────
    group_rows = ""
    for gname, g in GROUPS.items():
        clients_display = "모든 프로젝트" if g["clients"] == "all" else ", ".join(g["clients"])
        badge_class = "all" if g["clients"] == "all" else "tag"
        members = ", ".join(f"<code>{m}</code>" for m in g["members"])
        group_rows += (
            f"<tr><td><code>{gname}</code></td>"
            f"<td>{g['label']}</td>"
            f"<td>{members}</td>"
            f"<td><span class='{badge_class}'>{clients_display}</span></td></tr>"
        )

    # ── Employee table ────────────────────────────────────────────────────
    def _access_badge(emp_id: str) -> str:
        groups = _get_employee_groups(emp_id)
        if not groups:
            return '<span class="none">접근 권한 없음</span>'
        parts = []
        for gname in groups:
            clients = GROUPS[gname]["clients"]
            label = "모든 프로젝트" if clients == "all" else " + ".join(c.removeprefix("langflow-") for c in clients)
            cls = "all" if clients == "all" else "tag"
            parts.append(f'<span class="{cls}">{label}</span>')
        return " ".join(parts)

    emp_rows = "".join(
        f"<tr><td><code>{eid}</code></td><td>{e['name']}</td>"
        f"<td><code>{e['password']}</code></td><td>{_access_badge(eid)}</td></tr>"
        for eid, e in EMPLOYEES.items()
    )

    html = f"""
    <html><head><title>Mock Keycloak Admin</title>
    <style>
      body {{ font-family: sans-serif; padding:40px; background:#f0f4f8; }}
      h1 {{ color:#333; margin-bottom:4px; }}
      h2 {{ color:#555; margin:32px 0 12px; font-size:16px; }}
      .sub {{ color:#888; font-size:13px; margin-bottom:24px; }}
      table {{ border-collapse:collapse; background:#fff; border-radius:8px;
               box-shadow:0 2px 8px rgba(0,0,0,.08); width:100%; max-width:820px; margin-bottom:16px; }}
      th {{ background:#4a90d9; color:#fff; padding:10px 14px; text-align:left; font-size:13px; }}
      td {{ padding:9px 14px; border-bottom:1px solid #eee; vertical-align:middle; font-size:13px; }}
      tr:last-child td {{ border-bottom:none; }}
      .tag {{ display:inline-block; background:#e8f0fe; color:#1a56db;
              border-radius:10px; padding:1px 9px; font-size:12px; margin:1px; }}
      .all {{ display:inline-block; background:#d1fae5; color:#065f46;
              border-radius:10px; padding:1px 9px; font-size:12px; }}
      .none {{ display:inline-block; background:#fee2e2; color:#991b1b;
               border-radius:10px; padding:1px 9px; font-size:12px; }}
      code {{ background:#f0f0f0; padding:1px 5px; border-radius:3px; font-size:12px; }}
    </style></head>
    <body>
      <h1>🔑 Mock Keycloak Admin</h1>
      <p class="sub">Realm: <b>{REALM}</b> &nbsp;|&nbsp; {BASE_URL}</p>

      <h2>그룹 및 클라이언트 접근 권한</h2>
      <table>
        <thead><tr><th>Group</th><th>역할</th><th>멤버</th><th>접근 가능 클라이언트</th></tr></thead>
        <tbody>{group_rows}</tbody>
      </table>

      <h2>직원 목록 (EMP001~EMP010)</h2>
      <table>
        <thead><tr><th>사번</th><th>이름</th><th>Password</th><th>접근 가능 프로젝트</th></tr></thead>
        <tbody>{emp_rows}</tbody>
      </table>
    </body></html>
    """
    return HTMLResponse(html)


def _error_page(message: str) -> str:
    return f"""
    <html><head><title>접근 거부</title>
    <style>
      body {{ font-family:sans-serif; display:flex; justify-content:center;
              padding-top:80px; background:#f0f4f8; }}
      .box {{ background:#fff; padding:32px; border-radius:8px;
              box-shadow:0 2px 12px rgba(0,0,0,.12); width:380px; text-align:center; }}
      h3 {{ color:#dc2626; }} p {{ color:#555; line-height:1.6; }}
      a {{ color:#4a90d9; }}
    </style></head>
    <body><div class="box">
      <h3>❌ 로그인 실패</h3>
      <p>{message}</p>
      <p><a href="javascript:history.back()">← 돌아가기</a></p>
    </div></body></html>
    """


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
