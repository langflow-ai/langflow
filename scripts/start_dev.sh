#!/usr/bin/env bash
# Start multiple Langflow instances for local SSO testing.
# Usage: ./scripts/start_dev.sh
#
# Requires mock OIDC server to be running:
#   uv run scripts/mock_oidc_server.py
#
# First-time setup (cookie isolation between instances):
#   echo "127.0.0.1 project-a.localhost" | sudo tee -a /etc/hosts
#   echo "127.0.0.1 project-b.localhost" | sudo tee -a /etc/hosts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3.13 || command -v python3 || command -v python)"
fi

# Common OIDC settings (mock server)
MOCK_OIDC_URL="http://localhost:9000"

# Use subdomains so each instance has its own cookie namespace.
# (Browsers scope cookies by domain, not port — both instances on plain
#  localhost would share cookies and log each other out.)
HOST_A="project-a.localhost"
HOST_B="project-b.localhost"
PORT_A=7860
PORT_B=7861

# Verify /etc/hosts entries exist
for host in "$HOST_A" "$HOST_B"; do
  if ! grep -q "$host" /etc/hosts 2>/dev/null; then
    echo "⚠️  Missing /etc/hosts entry for $host"
    echo "   Run: echo '127.0.0.1 $host' | sudo tee -a /etc/hosts"
  fi
done

# Common Langflow settings
export LANGFLOW_AUTO_LOGIN=false
export LANGFLOW_REFRESH_SECURE=false
export LANGFLOW_REFRESH_SAME_SITE=lax
export LANGFLOW_ACCESS_SECURE=false
export LANGFLOW_ACCESS_SAME_SITE=lax

echo "Starting Langflow instances..."
echo "  project-a → http://$HOST_A:$PORT_A  (client: langflow-project-a)"
echo "  project-b → http://$HOST_B:$PORT_B  (client: langflow-project-b)"
echo ""
echo "Access groups:"
echo "  EMP001, EMP002 (langflow-admins)       → both instances"
echo "  EMP003-EMP005  (project-a-members)     → project-a only"
echo "  EMP006-EMP008  (project-b-members)     → project-b only"
echo "  EMP009, EMP010 (no group)              → no access"
echo ""
echo "Mock OIDC admin page: $MOCK_OIDC_URL/admin"
echo ""

# Clean up stale processes on target ports
for port in $PORT_A $PORT_B; do
  pid=$(lsof -ti :$port 2>/dev/null) && kill "$pid" 2>/dev/null && echo "Killed stale process on :$port" || true
done
sleep 1

# ── project-a instance ────────────────────────────────────────────────────────
(
  export KEYCLOAK_ENABLED=true
  export KEYCLOAK_SERVER_URL="$MOCK_OIDC_URL"
  export KEYCLOAK_REALM=company
  export KEYCLOAK_CLIENT_ID=langflow-project-a
  export KEYCLOAK_CLIENT_SECRET=secret-project-a
  export KEYCLOAK_REDIRECT_URI="http://$HOST_A:$PORT_A/api/v1/keycloak/callback"
  export KEYCLOAK_SHARED_USERNAME=langflow-shared-project-a
  export KEYCLOAK_BUTTON_TEXT="SSO 로그인"
  export LANGFLOW_DATABASE_URL="sqlite+aiosqlite:////tmp/langflow_project_a.db"
  export LANGFLOW_SECRET_KEY=dev-secret-project-a-000000000000
  export LANGFLOW_COOKIE_DOMAIN="$HOST_A"
  cd "$REPO_ROOT"
  "$PYTHON" -m langflow run --host 0.0.0.0 --port "$PORT_A" --no-open-browser 2>&1 | sed 's/^/[project-a] /'
) &
PID_A=$!

# ── project-b instance ────────────────────────────────────────────────────────
(
  export KEYCLOAK_ENABLED=true
  export KEYCLOAK_SERVER_URL="$MOCK_OIDC_URL"
  export KEYCLOAK_REALM=company
  export KEYCLOAK_CLIENT_ID=langflow-project-b
  export KEYCLOAK_CLIENT_SECRET=secret-project-b
  export KEYCLOAK_REDIRECT_URI="http://$HOST_B:$PORT_B/api/v1/keycloak/callback"
  export KEYCLOAK_SHARED_USERNAME=langflow-shared-project-b
  export KEYCLOAK_BUTTON_TEXT="SSO 로그인"
  export LANGFLOW_DATABASE_URL="sqlite+aiosqlite:////tmp/langflow_project_b.db"
  export LANGFLOW_SECRET_KEY=dev-secret-project-b-000000000000
  export LANGFLOW_COOKIE_DOMAIN="$HOST_B"
  cd "$REPO_ROOT"
  "$PYTHON" -m langflow run --host 0.0.0.0 --port "$PORT_B" --no-open-browser 2>&1 | sed 's/^/[project-b] /'
) &
PID_B=$!

# Graceful shutdown on Ctrl-C
trap 'echo ""; echo "Stopping instances..."; kill $PID_A $PID_B 2>/dev/null; wait' INT TERM

echo "Press Ctrl-C to stop all instances."
wait
