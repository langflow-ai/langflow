#!/usr/bin/env bash
set -Eeuo pipefail

#############################################
# Stop-First Docker Deploy w/ Nginx + TLS
# - Minimizes CPU/RAM: only one app container at a time
# - Safe rollback: restarts old container if new fails
# - Idempotent & CI/CD friendly
#############################################

# ---------- Logging + state ----------
CURRENT_STEP=""
DEPLOY_SUCCESS=0        # set to 1 only when deployment completes
CLEANED_UP=0            # guard to avoid double cleanup
SWITCHED=0              # set to 1 right after successful switch
STOPPED_ACTIVE=0        # set to 1 when we stop the active container
HAD_ACTIVE=0            # set to 1 if an active container existed

# ---------- Deploy status history rotation ----------
DEPLOY_ENV="/root/deploy_status.env"
DEPLOY_HISTORY="/root/deploy_status_history.env"
if [[ -f "$DEPLOY_ENV" ]]; then
  cat "$DEPLOY_ENV" >> "$DEPLOY_HISTORY"
  echo "" >> "$DEPLOY_HISTORY"
  rm -f "$DEPLOY_ENV"
fi

log()      { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }
ok()       { printf "\033[0;32m✅ %s\033[0m\n" "$*"; }
warn()     { printf "\033[0;33m⚠️  %s\033[0m\n" "$*"; }
err()      { printf "\033[0;31m❌ %s\033[0m\n" "$*"; }
step()     { CURRENT_STEP="$*"; log "$*"; }

# Traps: run cleanup on errors/interrupts/abnormal exit
trap 'err "Failed during: ${CURRENT_STEP:-unknown step}"; cleanup_on_failure; exit 1' ERR
trap 'warn "Interrupted (SIGINT/SIGTERM)"; cleanup_on_failure; exit 130' SIGINT SIGTERM
trap 'if [[ "$DEPLOY_SUCCESS" -ne 1 ]]; then warn "Exiting without success"; cleanup_on_failure; fi; report_status' EXIT

# ---------- Defaults ----------
APP_NAME="app"
CONFIG_FILE=""            # Script config .env (DOCKER_IMAGE, DOMAIN, etc)
DOCKER_IMAGE=""           # e.g. saravanakr/langflow:2.0.4
DOCKERHUB_USERNAME=""     # optional
DOCKERHUB_TOKEN=""        # optional
DOMAIN=""                 # e.g. demo.example.com
EMAIL=""                  # certbot email, default: admin@DOMAIN
CONTAINER_ENV_FILE=""     # passed to docker via --env-file
CONTAINER_PORT="7860"     # internal port inside container
BLUE_PORT="7861"          # host port for blue
GREEN_PORT="7862"         # host port for green
HEALTH_PATH="/health"     # path checked over HTTP
HEALTH_TIMEOUT="300"      # seconds
RETRY_MAX="5"
RETRY_SLEEP="5"
KEEP_OLD="1"              # keep old color container for quick rollback (1=yes, 0=no)
DB_USER=""
DB_PASSWORD=""
DB_NAME=""
VOLUME_NAME=""
# ---------- Parse args ----------
usage() {
  cat <<USAGE
Usage: $0 [--config <file>] [--image <repo:tag>] [--domain <domain>]
          [--docker-username <user>] [--docker-token <token>]
          [--env-file <path>] [--container-port <port>]
          [--blue-port <port>] [--green-port <port>]
          [--health-path </health>] [--email <you@domain>]
          [--db-user <user>] [--db-password <pass>] [--db-name <db>]
          [--volume-name <volume>] [--app-name <name>] [--prune-old]
USAGE
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)           CONFIG_FILE="${2:-}"; shift 2;;
    --image)            DOCKER_IMAGE="${2:-}"; shift 2;;
    --domain)           DOMAIN="${2:-}"; shift 2;;
    --docker-username)  DOCKERHUB_USERNAME="${2:-}"; shift 2;;
    --docker-token)     DOCKERHUB_TOKEN="${2:-}"; shift 2;;
    --env-file)         CONTAINER_ENV_FILE="${2:-}"; shift 2;;
    --container-port)   CONTAINER_PORT="${2:-}"; shift 2;;
    --blue-port)        BLUE_PORT="${2:-}"; shift 2;;
    --green-port)       GREEN_PORT="${2:-}"; shift 2;;
    --health-path)      HEALTH_PATH="${2:-}"; shift 2;;
    --email)            EMAIL="${2:-}"; shift 2;;
    --db-user)         DB_USER="${2:-}"; shift 2;;
    --db-password)     DB_PASSWORD="${2:-}"; shift 2;;
    --db-name)         DB_NAME="${2:-}"; shift 2;;
    --volume-name)     VOLUME_NAME="${2:-}"; shift 2;;
    --app-name)         APP_NAME="${2:-}"; shift 2;;
    --prune-old)        KEEP_OLD="0"; shift 1;;
    -h|--help)          usage;;
    *) err "Unknown option: $1"; usage;;
  esac
done

# ---------- Load script config .env (optional) ----------
# Allows: DOCKER_IMAGE=..., DOMAIN=..., DOCKERHUB_USERNAME=..., DOCKERHUB_TOKEN=..., CONTAINER_ENV_FILE=..., etc.
if [[ -n "${CONFIG_FILE}" ]]; then
  step "Loading config from ${CONFIG_FILE}"
  if [[ -f "${CONFIG_FILE}" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${CONFIG_FILE}"; set +a
    ok "Config loaded"
  else
    err "Config file not found: ${CONFIG_FILE}"; exit 1
  fi
fi

# ---------- Validate required inputs ----------
[[ -z "${DOCKER_IMAGE}" ]] && { err "--image (DOCKER_IMAGE) is required"; usage; }
[[ -z "${DOMAIN}" ]] && { err "--domain (DOMAIN) is required"; usage; }
[[ -z "${VOLUME_NAME}" ]] && { err "--volume-name is required"; usage; }
[[ -z "${EMAIL}" ]] && EMAIL="admin@${DOMAIN#www.}"

# ---------- Root check ----------
if [[ $EUID -ne 0 ]]; then
  err "Please run as root (sudo)."; exit 1
fi

# ---------- Helpers ----------
retry() {
  local tries="${1}"; shift
  local sleep_s="${1}"; shift
  local i
  for ((i=1; i<=tries; i++)); do
    if "$@"; then return 0; fi
    warn "Attempt ${i}/${tries} failed. Retrying in ${sleep_s}s..."
    sleep "${sleep_s}"
  done
  return 1
}

pkg_installed() { dpkg -s "$1" >/dev/null 2>&1; }
service_active() { systemctl is-active --quiet "$1"; }
docker_safe_rm() { docker rm -f "$1" >/dev/null 2>&1 || true; }
docker_exists()  { docker ps -a --format '{{.Names}}' | grep -Fxq "$1"; }
docker_running() { docker ps --format '{{.Names}}' | grep -Fxq "$1"; }

http_ok() {
  local url="$1"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)
  [[ "$code" -ge 200 && "$code" -lt 400 ]]
}

prepare_langflow_env() {
  [[ -n "$DB_USER" && -n "$DB_PASSWORD" && -n "$DB_NAME" ]] || {
    err "--db-user, --db-password and --db-name are required"; exit 1;
  }
  [[ -f "$CONTAINER_ENV_FILE" ]] || { err "Env file not found: $CONTAINER_ENV_FILE"; exit 1; }

  local PG_IMAGE="postgres@sha256:d0f363f8366fbc3f52d172c6e76bc27151c3d643b870e1062b4e8bfe65baf609"

  if ! docker image inspect "$PG_IMAGE" >/dev/null 2>&1; then
    step "Pulling required PostgreSQL image: $PG_IMAGE"
    docker pull "$PG_IMAGE"
    ok "PostgreSQL image pulled"
  else
    ok "PostgreSQL image already present"
  fi

  tail -c1 "$CONTAINER_ENV_FILE" | read -r _ || echo >> "$CONTAINER_ENV_FILE"

  if grep -q '^LANGFLOW_DATABASE_URL=' "$CONTAINER_ENV_FILE"; then
    sed -i "s|^LANGFLOW_DATABASE_URL=.*|LANGFLOW_DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@postgres:5432/$DB_NAME|" "$CONTAINER_ENV_FILE"
  else
    echo "LANGFLOW_DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@postgres:5432/$DB_NAME" >> "$CONTAINER_ENV_FILE"
  fi

  if ! grep -q '^POSTGRES_IMAGE=' "$CONTAINER_ENV_FILE"; then
    echo "POSTGRES_IMAGE=$PG_IMAGE" >> "$CONTAINER_ENV_FILE"
  fi

  if grep -q '^LANGFLOW_CONFIG_DIR=' "$CONTAINER_ENV_FILE"; then
    sed -i "s|^LANGFLOW_CONFIG_DIR=.*|LANGFLOW_CONFIG_DIR=/app/langflow|" "$CONTAINER_ENV_FILE"
  else
    echo "LANGFLOW_CONFIG_DIR=/app/langflow" >> "$CONTAINER_ENV_FILE"
  fi

  if grep -q '^LANGFLOW_SAVE_DB_IN_CONFIG_DIR=' "$CONTAINER_ENV_FILE"; then
    sed -i "s|^LANGFLOW_SAVE_DB_IN_CONFIG_DIR=.*|LANGFLOW_SAVE_DB_IN_CONFIG_DIR=false|" "$CONTAINER_ENV_FILE"
  else
    echo "LANGFLOW_SAVE_DB_IN_CONFIG_DIR=false" >> "$CONTAINER_ENV_FILE"
  fi
}

# ---------- Docker cleanup (keep last 2 images only) ----------
cleanup_old_images() {
  step "Cleaning up old Docker images (keeping last 2)"
  local PG_IMAGE
  if [[ -f "$CONTAINER_ENV_FILE" ]]; then
    PG_IMAGE=$(grep '^POSTGRES_IMAGE=' "$CONTAINER_ENV_FILE" | cut -d'=' -f2- || true)
    if [[ -n "$PG_IMAGE" ]]; then
      ok "POSTGRES_IMAGE is present in env file"
    else
      ok "No POSTGRES_IMAGE found in env file"
    fi
  fi

  local images
  images=$(docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedAt}}' \
    | sort -k3 -r \
    | awk 'NR>2 {print $2}')

  if [[ -n "$images" ]]; then
    for img in $images; do
      if [[ -n "$PG_IMAGE" ]] && docker image inspect "$img" >/dev/null 2>&1; then
        if docker image inspect --format='{{index .RepoDigests 0}}' "$img" 2>/dev/null | grep -q "$PG_IMAGE"; then
          ok "Skipping Postgres image to delete"
          continue
        fi
      fi
      # Try to remove other images
      docker rmi -f "$img" >/dev/null 2>&1 || true
    done
    ok "Old images removed (pinned Postgres preserved)"
  else
    ok "No old images to remove"
  fi
}

# ---------- Ensure EBS Volume is Mounted ----------
ensure_ebs_volume() {
    step "Ensuring EBS volume is mounted and configured"

    # 1️ Detect environment and pick correct volume
    if [[ "$DOMAIN" == *"staging."* ]]; then
        ENVIRONMENT="staging"
    else
        ENVIRONMENT="prod"
    fi
    ok "Detected environment: ${ENVIRONMENT}"

    # 2 Define paths
    local SYSTEM_MOUNT_POINT="/mnt/${VOLUME_NAME}"
    local APP_MOUNT_POINT="/app/ebsstorage"
    local VOLUME_DEVICE="/dev/disk/by-id/scsi-0DO_Volume_${VOLUME_NAME}"
    local LANGFLOW_STORAGE_PATH="${APP_MOUNT_POINT}/langflowstorage"
    local POSTGRES_STORAGE_PATH="${APP_MOUNT_POINT}/postgres"

    # 3 Ensure system-level mount exists
    if mountpoint -q "${SYSTEM_MOUNT_POINT}"; then
        ok "Volume already mounted at ${SYSTEM_MOUNT_POINT}"
    else
        warn "Volume not mounted. Attempting to mount..."
        mkdir -p "${SYSTEM_MOUNT_POINT}"
        mount -o discard,defaults,noatime "${VOLUME_DEVICE}" "${SYSTEM_MOUNT_POINT}"
        ok "Mounted ${VOLUME_DEVICE} → ${SYSTEM_MOUNT_POINT}"

        # Ensure persistence after reboot
        if ! grep -qs "${VOLUME_DEVICE}" /etc/fstab; then
            echo "${VOLUME_DEVICE} ${SYSTEM_MOUNT_POINT} ext4 defaults,nofail,discard 0 0" >> /etc/fstab
            ok "Added fstab entry for persistence"
        else
            ok "fstab entry already exists"
        fi
    fi

    # 4️ Bind system mount to /app/ebsstorage
    if mountpoint -q "${APP_MOUNT_POINT}"; then
        ok "/app/ebsstorage already points to ${SYSTEM_MOUNT_POINT}"
    else
        mkdir -p "${APP_MOUNT_POINT}"
        mount --bind "${SYSTEM_MOUNT_POINT}" "${APP_MOUNT_POINT}" || {
            warn "Bind mount failed; creating symlink instead"
            ln -sfn "${SYSTEM_MOUNT_POINT}" "${APP_MOUNT_POINT}"
        }
        ok "Linked ${SYSTEM_MOUNT_POINT} → ${APP_MOUNT_POINT}"
    fi

    # 5️ Verify subdirectories
    for dir in "${LANGFLOW_STORAGE_PATH}" "${POSTGRES_STORAGE_PATH}"; do
        if [ -d "$dir" ]; then
            ok "Storage directory already exists: $dir"
        else
            mkdir -p "$dir"
            ok "Created storage directory: $dir"
        fi
    done

    # 6️ Detect container UID/GID if exists
    local CONTAINER_UID=1000
    local CONTAINER_GID=1000

    # 7️ Apply correct permissions
    chown -R "${CONTAINER_UID}:${CONTAINER_GID}" "${LANGFLOW_STORAGE_PATH}"
    chown -R 999:999 "${POSTGRES_STORAGE_PATH}" # Postgres often runs as UID 999
    ok "Permissions set for Docker (Langflow UID:${CONTAINER_UID}, Postgres UID:999)"

    ok "✅ EBS volume ready and linked: ${SYSTEM_MOUNT_POINT} → ${APP_MOUNT_POINT}"
}


# Paths used by Nginx toggling
NGINX_SITE="/etc/nginx/sites-available/${APP_NAME}.conf"
NGINX_SITE_LINK="/etc/nginx/sites-enabled/${APP_NAME}.conf"
SNIPPETS_DIR="/etc/nginx/snippets"
UP_BLUE="${SNIPPETS_DIR}/${APP_NAME}-upstream-blue.conf"
UP_GREEN="${SNIPPETS_DIR}/${APP_NAME}-upstream-green.conf"
UP_ACTIVE="${SNIPPETS_DIR}/${APP_NAME}-upstream-active.conf"
PROXY_SNIPPET="${SNIPPETS_DIR}/${APP_NAME}-proxy.conf"
CERT_ROOT="/var/www/certbot"

ACTIVE_FILE="/var/run/${APP_NAME}-active-color" # stores "blue" or "green"

# ---------- Install system deps (idempotent) ----------
step "Updating apt package index"; apt-get update -y; ok "apt updated"

install_if_missing() {
  local pkg="$1"
  if ! pkg_installed "$pkg"; then
    step "Installing ${pkg}"
    DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg"
    ok "${pkg} installed"
  else
    ok "${pkg} already installed"
  fi
}

install_if_missing curl
install_if_missing jq
install_if_missing nginx
install_if_missing certbot
install_if_missing python3-certbot-nginx
install_if_missing docker.io

step "Enabling & starting Docker and Nginx"
systemctl enable docker >/dev/null 2>&1 || true
systemctl start docker || true
systemctl enable nginx >/dev/null 2>&1 || true
service_active nginx || systemctl start nginx
ok "Services ensured"

# ---------- Docker login (optional) ----------
if [[ -n "${DOCKERHUB_USERNAME}" && -n "${DOCKERHUB_TOKEN}" ]]; then
  step "Docker Hub login"
  echo "${DOCKERHUB_TOKEN}" | docker login --username "${DOCKERHUB_USERNAME}" --password-stdin
  ok "Logged in to Docker Hub"
else
  step "Skipping Docker Hub login"
fi

# Quick sanity check that the daemon is reachable
docker info >/dev/null 2>&1 || { err "Docker daemon not reachable"; exit 1; }
ok "Docker daemon reachable"

# ---------- Pull image (with retries) ----------
cleanup_old_images
step "Pulling Docker image: ${DOCKER_IMAGE}"
retry "${RETRY_MAX}" "${RETRY_SLEEP}" docker pull "${DOCKER_IMAGE}"
ok "Image pulled"

# ---------- Determine colors & names ----------
get_symlink_color() {
  if [[ -L "${UP_ACTIVE}" ]]; then
    readlink -f "${UP_ACTIVE}" | grep -q "blue" && echo "blue" && return
    readlink -f "${UP_ACTIVE}" | grep -q "green" && echo "green" && return
  fi
  echo ""
}

ACTIVE_COLOR=""
[[ -f "${ACTIVE_FILE}" ]] && ACTIVE_COLOR="$(cat "${ACTIVE_FILE}" || true)"
[[ -z "${ACTIVE_COLOR}" ]] && ACTIVE_COLOR="$(get_symlink_color)"
[[ -z "${ACTIVE_COLOR}" ]] && ACTIVE_COLOR="green"   # default first active

if [[ "${ACTIVE_COLOR}" == "blue" ]]; then
  TARGET_COLOR="green"; TARGET_PORT="${GREEN_PORT}"
else
  TARGET_COLOR="blue";  TARGET_PORT="${BLUE_PORT}"
fi

ACTIVE_NAME="${APP_NAME}_${ACTIVE_COLOR}"
TARGET_NAME="${APP_NAME}_${TARGET_COLOR}"

docker_exists "${ACTIVE_NAME}" && HAD_ACTIVE=1 || HAD_ACTIVE=0

ok "Active color: ${ACTIVE_COLOR:-none} (container: ${ACTIVE_NAME}); Target: ${TARGET_COLOR} on port ${TARGET_PORT}"

# ---------- SSL helpers & Nginx ----------
ensure_ssl_support_files() {
  if [[ ! -f "/etc/letsencrypt/options-ssl-nginx.conf" ]]; then
    step "Downloading options-ssl-nginx.conf"
    curl -fsSL https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
      -o /etc/letsencrypt/options-ssl-nginx.conf
    ok "Downloaded options-ssl-nginx.conf"
  fi
  if [[ ! -f "/etc/letsencrypt/ssl-dhparams.pem" ]]; then
    step "Downloading ssl-dhparams.pem"
    curl -fsSL https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
      -o /etc/letsencrypt/ssl-dhparams.pem
    ok "Downloaded ssl-dhparams.pem"
  fi
}

ensure_snippets() {
  step "Ensuring Nginx upstream & proxy snippets"
  mkdir -p "${SNIPPETS_DIR}" "${CERT_ROOT}"

  cat > "${UP_BLUE}" <<EOF
upstream ${APP_NAME}_upstream {
    server 127.0.0.1:${BLUE_PORT};
    keepalive 32;
}
EOF
  cat > "${UP_GREEN}" <<EOF
upstream ${APP_NAME}_upstream {
    server 127.0.0.1:${GREEN_PORT};
    keepalive 32;
}
EOF
  cat > "${PROXY_SNIPPET}" <<'EOF'
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_read_timeout 300;
proxy_send_timeout 300;
EOF

  [[ ! -L "${UP_ACTIVE}" ]] && ln -sf "${UP_GREEN}" "${UP_ACTIVE}"
  ok "Snippets ready"
}

write_site_http_only() {
  cat > "${NGINX_SITE}" <<EOF
include ${UP_ACTIVE};
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    location ^~ /.well-known/acme-challenge/ { root ${CERT_ROOT}; }
    location / { return 301 https://\$host\$request_uri; }
}
EOF
}

write_site_https() {
  cat > "${NGINX_SITE}" <<EOF
include ${UP_ACTIVE};

server {
  listen 80;
  server_name ${DOMAIN} www.${DOMAIN};
  location ^~ /.well-known/acme-challenge/ { root ${CERT_ROOT}; }
  location / { return 301 https://\$host\$request_uri; }
}

server {
  listen 443 ssl; http2 on;
  server_name ${DOMAIN};
  ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
  include /etc/letsencrypt/options-ssl-nginx.conf;
  ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

  location / {
    proxy_pass http://${APP_NAME}_upstream;
    include ${PROXY_SNIPPET};
  }
}

server {
  listen 443 ssl; http2 on;
  server_name www.${DOMAIN};
  ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
  include /etc/letsencrypt/options-ssl-nginx.conf;
  ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
  return 301 https://${DOMAIN}\$request_uri;
}
EOF
}

ensure_nginx() {
  ensure_snippets
  mkdir -p "$(dirname "${NGINX_SITE}")" /etc/nginx/sites-enabled
  local have_cert="0"
  [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]] && have_cert="1"

  step "Writing Nginx site config (certs present: ${have_cert})"
  if [[ "${have_cert}" == "1" ]]; then
    ensure_ssl_support_files
    write_site_https
  else
    write_site_http_only
  fi

  ln -sf "${NGINX_SITE}" "${NGINX_SITE_LINK}"
  rm -f /etc/nginx/sites-enabled/default || true

  step "Testing Nginx config"
  nginx -t
  if service_active nginx; then systemctl reload nginx; else systemctl start nginx; fi
  ok "Nginx config applied"
}

# ---------- Certbot timer (robust) ----------
ensure_certbot_timer() {
  step "Ensuring Certbot auto-renewal timer"

  _any_timer_active() {
    systemctl is-active --quiet certbot.timer && return 0
    systemctl is-active --quiet snap.certbot.renew.timer && return 0
    systemctl is-active --quiet certbot-renew.timer && return 0
    return 1
  }

  # Already active?
  if _any_timer_active; then
    ok "Certbot auto-renewal timer already active"
    return 0
  fi

  # Ensure /usr/bin/certbot exists (snap installs to /snap/bin/certbot)
  if [[ ! -x /usr/bin/certbot && -x /snap/bin/certbot ]]; then
    ln -sf /snap/bin/certbot /usr/bin/certbot
  fi

  # Try enabling known timers
  if systemctl list-unit-files --no-pager | grep -q '^certbot.timer'; then
    systemctl enable --now certbot.timer
  elif systemctl list-unit-files --no-pager | grep -q '^snap.certbot.renew.timer'; then
    systemctl enable --now snap.certbot.renew.timer
  else
    # Fallback: create our own twice-daily timer
    warn "No built-in Certbot timer found; creating certbot-renew.timer"
    cat >/etc/systemd/system/certbot-renew.service <<'EOF'
[Unit]
Description=Certbot Renew

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot -q renew
EOF

    cat >/etc/systemd/system/certbot-renew.timer <<'EOF'
[Unit]
Description=Run certbot renew twice daily

[Timer]
OnCalendar=*-*-* 00,12:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

    systemctl daemon-reload
    systemctl enable --now certbot-renew.timer
  fi

  # Final verification
  if _any_timer_active; then
    ok "Certbot auto-renewal timer active"
    return 0
  fi

  # Last resort: start again and recheck
  systemctl start certbot.timer 2>/dev/null || true
  systemctl start snap.certbot.renew.timer 2>/dev/null || true
  systemctl start certbot-renew.timer 2>/dev/null || true
  sleep 1

  if _any_timer_active; then
    ok "Certbot auto-renewal timer active"
  else
    err "Certbot auto-renewal timer NOT active"
    systemctl list-timers --no-pager --all | sed -n '1,200p' || true
    exit 1
  fi
}

ensure_certbot_deploy_hook() {
  step "Ensuring Certbot deploy hook reloads Nginx"
  local hook_dir="/etc/letsencrypt/renewal-hooks/deploy"
  local hook_file="${hook_dir}/000-reload-nginx.sh"

  mkdir -p "${hook_dir}"

  cat > "${hook_file}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
systemctl reload nginx
EOF

  chmod +x "${hook_file}"
  ok "Certbot deploy hook installed: ${hook_file}"
}

issue_cert_if_needed() {
  if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
    ok "TLS certificate already exists"
    ensure_certbot_timer
    ensure_certbot_deploy_hook
    step "Verifying certbot timer"
    if systemctl is-active --quiet certbot.timer || \
       systemctl is-active --quiet snap.certbot.renew.timer || \
       systemctl is-active --quiet certbot-renew.timer; then
      ok "Certbot auto-renewal timer active"
    else
      err "Certbot auto-renewal timer NOT active"
      systemctl list-timers --no-pager --all | sed -n '1,200p' || true
      exit 1
    fi
    return
  fi

  step "Issuing Let's Encrypt certificate (webroot)"
  ensure_nginx
  certbot certonly --webroot -w "${CERT_ROOT}" -d "${DOMAIN}" -d "www.${DOMAIN}" \
    --email "${EMAIL}" --agree-tos --non-interactive
  ok "Certificate issued"
  ensure_ssl_support_files
  ensure_nginx

  ensure_certbot_timer
  ensure_certbot_deploy_hook
  step "Verifying certbot timer"
  if systemctl is-active --quiet certbot.timer || \
     systemctl is-active --quiet snap.certbot.renew.timer || \
     systemctl is-active --quiet certbot-renew.timer; then
    ok "Certbot auto-renewal timer active"
  else
    err "Certbot auto-renewal timer NOT active"
    systemctl list-timers --no-pager --all | sed -n '1,200p' || true
    exit 1
  fi
}

# ---------- Traffic switching (only after health passes) ----------
switch_traffic() {
  step "Switching Nginx upstream to ${TARGET_COLOR} (port ${TARGET_PORT})"
  if [[ "${TARGET_COLOR}" == "blue" ]]; then
    ln -sf "${UP_BLUE}" "${UP_ACTIVE}"
  else
    ln -sf "${UP_GREEN}" "${UP_ACTIVE}"
  fi
  echo "${TARGET_COLOR}" > "${ACTIVE_FILE}"
  nginx -t
  systemctl reload nginx
  ok "Switched traffic to ${TARGET_COLOR}"
  SWITCHED=1
}

verify_domain() {
  step "Verifying domain is serving over HTTPS: https://${DOMAIN}"
  local deadline=$((SECONDS + 120))
  while (( SECONDS < deadline )); do
    if http_ok "https://${DOMAIN}"; then
      ok "Domain reachable over HTTPS"
      return 0
    fi
    sleep 2
  done
  err "Domain did not become healthy over HTTPS"
  return 1
}

rollback_switch() {
  step "Rolling back Nginx to ${ACTIVE_COLOR}"
  if [[ "${ACTIVE_COLOR}" == "blue" ]]; then
    ln -sf "${UP_BLUE}" "${UP_ACTIVE}"
  else
    ln -sf "${UP_GREEN}" "${UP_ACTIVE}"
  fi
  nginx -t
  systemctl reload nginx
  ok "Rollback complete"
}

cleanup_old_container() {
  if [[ "${KEEP_OLD}" == "0" && "${HAD_ACTIVE}" -eq 1 ]]; then
    local old="${ACTIVE_NAME}"
    step "Pruning old container ${old}"
    docker_safe_rm "${old}"
    ok "Old container removed"
  else
    ok "Keeping old container for quick rollback"
  fi
}

# ---------- Ensure PostgreSQL and network ----------
ensure_postgres() {
  step "Ensuring PostgreSQL container"

  # Ensure network exists
  docker network inspect langflow-net >/dev/null 2>&1 || docker network create langflow-net

  # Load image from env if missing
  if [[ -z "${POSTGRES_IMAGE:-}" ]]; then
    POSTGRES_IMAGE=$(grep '^POSTGRES_IMAGE=' "$CONTAINER_ENV_FILE" | cut -d= -f2-)
  fi

  # Case 1: Container exists
  if docker_exists "postgres"; then
    if docker_running "postgres"; then
      # Container is running — verify mount
      local current_mount
      current_mount=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Source}}{{end}}{{end}}' postgres 2>/dev/null || true)

      if [[ "${current_mount}" == "/app/ebsstorage/postgres" ]]; then
        ok "PostgreSQL container already running with correct bind mount"
        return 0
      else
        warn "Incorrect mount (${current_mount:-none}) detected — recreating container"
      fi
    else
      # Container exists but not running — clean up before recreating
      warn "PostgreSQL container exists but is stopped — removing stale container"
    fi

    # Stop & remove container safely
    docker stop postgres >/dev/null 2>&1 || true
    docker rm -f postgres >/dev/null 2>&1 || true

    # Remove lingering named volume
    if docker volume inspect langflow-postgres >/dev/null 2>&1; then
      step "Removing old named volume 'langflow-postgres'"
      docker volume rm -f langflow-postgres >/dev/null 2>&1 || true
    fi
  fi

  # Case 2: Start a fresh container
  step "Starting PostgreSQL container with correct bind mount"
  docker run -d \
    --name postgres \
    --network langflow-net \
    -e POSTGRES_USER="${DB_USER}" \
    -e POSTGRES_PASSWORD="${DB_PASSWORD}" \
    -e POSTGRES_DB="${DB_NAME}" \
    -v /app/ebsstorage/postgres:/var/lib/postgresql/data \
    --restart unless-stopped \
    "${POSTGRES_IMAGE}"

  ok "PostgreSQL container started with correct bind mount"
}

# ---------- Start/stop containers (STOP-FIRST) ----------
stop_active_container() {
  if [[ "${HAD_ACTIVE}" -eq 1 ]]; then
    if docker_running "${ACTIVE_NAME}"; then
      step "Stopping active container ${ACTIVE_NAME}"
      docker stop "${ACTIVE_NAME}" >/dev/null
      STOPPED_ACTIVE=1
      ok "Stopped ${ACTIVE_NAME}"
    else
      warn "Active container ${ACTIVE_NAME} not running"
    fi
  else
    ok "No previously active container found (first deploy?)"
  fi
}

start_target_container() {
  step "Launching target ${TARGET_COLOR} container: ${TARGET_NAME} on host port ${TARGET_PORT}"
  docker_safe_rm "${TARGET_NAME}"

  local run_cmd=( docker run -d
    --restart unless-stopped
    --name "${TARGET_NAME}"
    -l "app=${APP_NAME}"
    -l "color=${TARGET_COLOR}"
    -p "${TARGET_PORT}:${CONTAINER_PORT}"
    --network langflow-net
    -v /app/ebsstorage/langflowstorage:/app/langflow
  )

  if [[ -n "${CONTAINER_ENV_FILE}" ]]; then
    [[ -f "${CONTAINER_ENV_FILE}" ]] || { err "Container env file not found: ${CONTAINER_ENV_FILE}"; exit 1; }
    run_cmd+=( --env-file "${CONTAINER_ENV_FILE}" )
  fi

  run_cmd+=( "${DOCKER_IMAGE}" )
  "${run_cmd[@]}"
  ok "Container started"
}

wait_until_healthy() {
  step "Health-checking ${TARGET_NAME}"
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  local has_healthcheck="0"
  local last_log=0
  local status="starting"

  if docker inspect --format '{{if .Config.Healthcheck}}yes{{else}}no{{end}}' "${TARGET_NAME}" 2>/dev/null | grep -q yes; then
    has_healthcheck="1"; ok "Docker HEALTHCHECK detected; waiting for 'healthy'"
  else
    warn "No Docker HEALTHCHECK; will use HTTP ${HEALTH_PATH}"
  fi

  while (( SECONDS < deadline )); do
    if [[ "${has_healthcheck}" == "1" ]]; then
      status=$(docker inspect --format '{{.State.Health.Status}}' "${TARGET_NAME}" 2>/dev/null || echo "starting")
      [[ "${status}" == "healthy" ]] && { ok "Container healthy"; return 0; }
      [[ "${status}" == "unhealthy" ]] && { err "Container reported UNHEALTHY"; return 1; }
    fi

    if http_ok "http://127.0.0.1:${TARGET_PORT}${HEALTH_PATH}"; then
      ok "HTTP health OK"; return 0
    fi

    if (( SECONDS - last_log >= 10 )); then
      log "Waiting for container health... retrying in 2s (elapsed: $((SECONDS - (deadline - HEALTH_TIMEOUT)))s)"
      last_log=$SECONDS
    fi
    sleep 2
  done

  err "Health check timed out after ${HEALTH_TIMEOUT}s"
  return 1
}

# ---------- Cleanup on failure / interrupt ----------
cleanup_on_failure() {
  [[ "${CLEANED_UP}" -eq 1 ]] && return 0
  CLEANED_UP=1
  warn "Running failure cleanup"

  # If we switched traffic already, roll back Nginx to previous color
  if [[ "${SWITCHED}" -eq 1 ]]; then
    rollback_switch || true
  fi

  # Kill the target container if it exists (failed health/verify or interrupt)
  if docker_exists "${TARGET_NAME}"; then
    warn "Removing target container ${TARGET_NAME}"
    docker rm -f "${TARGET_NAME}" >/dev/null 2>&1 || true
  fi

  # If we had stopped the active one but haven't switched yet, bring it back up
  if [[ "${STOPPED_ACTIVE}" -eq 1 && "${HAD_ACTIVE}" -eq 1 && ! $(docker_running "${ACTIVE_NAME}" && echo yes) ]]; then
    warn "Restarting previous active container ${ACTIVE_NAME}"
    docker start "${ACTIVE_NAME}" >/dev/null 2>&1 || true
  fi

  ok "Failure cleanup completed"
}

# ---------- Final reporting ----------
report_status() {
  local status desc running
  running=$(docker ps --filter "name=${APP_NAME}_" --format "{{.Names}} {{.Image}}" | head -n1 || true)

  if [[ "$DEPLOY_SUCCESS" -eq 1 ]]; then
    status="success"
    desc="Deployment succeeded"
  elif [[ "$STOPPED_ACTIVE" -eq 1 && "$HAD_ACTIVE" -eq 1 ]]; then
    status="failure"
    desc="Deployment failed, rolled back"
  elif [[ -n "$running" ]]; then
    status="failure"
    desc="Deployment failed. Older container live"
  else
    status="failure"
    desc="Deployment failed. No container running"
  fi

  {
    echo "FINAL_STATUS=\"$status\""
    echo "FINAL_DESCRIPTION=\"${desc:0:140}\""
    echo "FINAL_CONTAINER=\"$running\""
  } > /root/deploy_status.env
}

# ---------- Execute flow (STOP-FIRST) ----------
ensure_nginx
issue_cert_if_needed
ensure_ebs_volume

# Prepare but DO NOT switch Nginx yet. We will switch only after new target is healthy.
# 1) Stop active (frees CPU/RAM/port)
stop_active_container
prepare_langflow_env
ensure_postgres

# 2) Start target and health-check while site is temporarily down
start_target_container
wait_until_healthy

# 3) Switch traffic and finalize
switch_traffic
verify_domain

# 4) Success → optionally prune old container
ok "Deployment successful: ${TARGET_COLOR} is live"
cleanup_old_container
DEPLOY_SUCCESS=1
