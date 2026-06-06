# Lothal deployment runbook

How the Lothal site is hosted on the RackNerd box, how to bring up the stack, and
how to operate it. Pairs with `docker-compose.prod.yml` (root) and
`deploy/nginx/lothal.conf`.

## Architecture

```
Internet ──HTTPS──▶ host nginx (:443, Let's Encrypt TLS)
                        │  reverse-proxy
                        ▼
                 127.0.0.1:8080  ── frontend container (nginx)
                        │  proxies /api, /health
                        ▼
                 backend container (:7860, langflow --backend-only)
                        │
                        ▼
                 db container (postgres:16-trixie, internal only)
```

Only the host nginx is public (`:80`/`:443`, opened by ufw "Nginx Full"). The frontend
is published to `127.0.0.1:8080` (loopback only); backend and Postgres stay on the
internal compose network. TLS terminates at the host nginx.

## Server facts

- Host: RackNerd, `107.172.168.104`, hostname `racknerd-09d9783`.
- OS: Ubuntu 24.04 LTS, 3 vCPU, 3.8 GB RAM (+2 GB swap), ~55 GB free.
- Deploy user: `lothal` (in `sudo` + `docker` groups).
- App directory: `/opt/lothal/` (owned by `lothal`) — holds `docker-compose.prod.yml` + `.env`.
- A standalone `clewdr` install in `~/clewdr` is unrelated to Lothal and left untouched
  (manual-launch only; uses ports 8000/8001/8484 — no overlap with Lothal).

## One-time server bootstrap

Performed once on a fresh box (idempotent — safe to re-run):

1. **Swap** — 2 GB swap present (`swapon --show`); RAM is modest, swap is the safety margin.
2. **Idle host services removed** — the pre-existing host Postgres was stopped + disabled
   (`systemctl disable --now postgresql`); Lothal uses its own containerized Postgres.
3. **Docker** — installed via `https://get.docker.com`; `lothal` added to the `docker`
   group; `docker` enabled at boot. Includes the compose plugin (`docker compose`).
4. **certbot** — `apt-get install certbot python3-certbot-nginx`; `certbot.timer` auto-renews.
5. **Deploy SSH key** — an ed25519 key authorizes `lothal` for non-interactive SSH/CI.
   The private key is the `SSH_KEY` GitHub secret (see below).
6. **App dir** — `/opt/lothal/` created and `chown lothal:lothal`; compose + `.env` placed there.

## nginx + TLS (host)

DNS for the domain must point at `107.172.168.104` first. Then:

```bash
DOMAIN=lothal.example.com           # <-- the real domain
sudo cp /opt/lothal/lothal.conf /etc/nginx/sites-available/lothal.conf
sudo sed -i "s/__DOMAIN__/$DOMAIN/g" /etc/nginx/sites-available/lothal.conf
# Obtain the cert (cert only; does not rewrite our config):
sudo certbot certonly --nginx -d "$DOMAIN" --non-interactive --agree-tos -m admin@$DOMAIN
# Enable our site, drop the stock default:
sudo ln -sf /etc/nginx/sites-available/lothal.conf /etc/nginx/sites-enabled/lothal.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Renewal is automatic via `certbot.timer` (nginx authenticator). Test with
`sudo certbot renew --dry-run`.

## Create the production .env

```bash
cd /opt/lothal
cp .env.prod.example .env   # if not already present
# Fill every __CHANGE_ME__. Generate strong values:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # LANGFLOW_SECRET_KEY
# Set POSTGRES_PASSWORD (and mirror it inside LANGFLOW_DATABASE_URL),
# LANGFLOW_SUPERUSER_PASSWORD, and the OPENAI_BASE_URL / OPENAI_API_KEY / LOTHAL_MODEL_NAME.
chmod 600 .env
```

## GHCR login (to pull private images)

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
```

Use a GitHub PAT (or `GITHUB_TOKEN` in CI) with `read:packages`. Skip if the images are public.

## Deploy / redeploy (manual)

```bash
cd /opt/lothal
docker compose -f docker-compose.prod.yml pull
# Run DB migrations before starting the new backend:
docker compose -f docker-compose.prod.yml run --rm backend python -m langflow migration --fix
docker compose -f docker-compose.prod.yml up -d
# Health check:
curl -fsS https://$DOMAIN/health && echo " OK"
```

The automated equivalent (build → GHCR → SSH → migrate → up → health-check) is the
GitHub Actions `workflow_dispatch` deploy job (story C.3).

## GitHub Actions secrets (for the C.3 deploy workflow)

| Secret | Value |
|---|---|
| `SSH_HOST` | `107.172.168.104` |
| `SSH_USER` | `lothal` |
| `SSH_KEY` | private half of the deploy ed25519 key |
| `GHCR_TOKEN` | PAT with `write:packages` (build/push) — CI may use the built-in `GITHUB_TOKEN` |
| prod env values | `POSTGRES_PASSWORD`, `LANGFLOW_SECRET_KEY`, `LANGFLOW_SUPERUSER_PASSWORD`, `OPENAI_*`, `LOTHAL_MODEL_NAME` (or maintain `/opt/lothal/.env` directly on the box) |

## Operations

```bash
cd /opt/lothal
docker compose -f docker-compose.prod.yml ps                  # status
docker compose -f docker-compose.prod.yml logs -f backend     # logs
docker compose -f docker-compose.prod.yml restart backend     # restart a service
docker compose -f docker-compose.prod.yml down                # stop the stack (keeps volumes)

# Postgres backup:
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup-$(date +%F).sql
```

Data lives in named volumes `lothal-db-data` (Postgres) and `lothal-langflow-data`
(`/app/langflow`: secret_key, etc.). Don't `docker compose down -v` in production — that
deletes them.
