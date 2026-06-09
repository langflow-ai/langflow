# Lothal deployment runbook

How the Lothal site is hosted on the RackNerd box, how to bring up the stack from a
fresh server, and how to operate it. Pairs with `docker-compose.prod.yml` (repo root),
`deploy/.env.prod.example`, and `deploy/nginx/lothal.conf`.

The live domain is **`lothal.app`** (DNS at Porkbun → `107.172.168.104`). Substitute your
own domain anywhere `lothal.app` appears if deploying elsewhere.

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
- Deploy user: `lothal` (in `sudo` + `docker` groups). `sudo` is **password-prompted**, not
  passwordless — the bootstrap steps below are run interactively; the automated C.3 deploy
  never needs `sudo` (it only runs `docker compose`, which `lothal` can do via the `docker` group).
- App directory: `/opt/lothal/` (owned by `lothal`) — holds `docker-compose.prod.yml`,
  `.env`, `.env.prod.example`, and `lothal.conf`.
- A standalone `clewdr` install in `~/clewdr` is unrelated to Lothal and left untouched
  (manual-launch only; uses ports 8000/8001/8484 — no overlap with Lothal).

## One-time server bootstrap

Performed once on a fresh box (every step is idempotent — safe to re-run). Run as a sudo-capable
user; the deploy user is named `lothal` below.

1. **Swap** — ensure ≥2 GB swap (`swapon --show`); RAM is modest, swap is the safety margin.
   ```bash
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```
   (The current box uses a 2 GB swap *partition* `/dev/vda3` instead — either is fine.)
2. **Idle host services removed** — stop + disable any pre-existing host Postgres; Lothal uses
   its own containerized Postgres on the internal network.
   ```bash
   sudo systemctl disable --now postgresql 2>/dev/null || true
   ```
3. **Docker** — install Engine + compose plugin and let `lothal` use it without sudo:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker lothal      # log out/in (or `newgrp docker`) to pick up the group
   sudo systemctl enable --now docker
   ```
4. **certbot** — `sudo apt-get install -y certbot python3-certbot-nginx nginx`; `certbot.timer`
   auto-renews (verify with `systemctl is-enabled certbot.timer`).
5. **Deploy SSH key** — an ed25519 key authorizes `lothal` for non-interactive SSH/CI. Its
   public half goes in `/home/lothal/.ssh/authorized_keys`; its **private** half is the `SSH_KEY`
   GitHub secret (see [GitHub Actions secrets](#github-actions-secrets-for-the-c3-deploy-workflow)).
6. **App dir + deploy files** — create the dir and copy the three deploy files in. The repo is
   private, so the simplest path is to `scp` them from a local checkout (the same machine that
   holds the SSH key):
   ```bash
   # on the server:
   sudo install -d -o lothal -g lothal /opt/lothal

   # from a local checkout of realbytecode/langflow (dev branch):
   scp docker-compose.prod.yml deploy/.env.prod.example deploy/nginx/lothal.conf \
       lothal@107.172.168.104:/opt/lothal/
   ```
   (Alternative: clone the repo on the box with a read-only deploy key/PAT if you want it to
   self-update.) After this, `/opt/lothal/` holds `docker-compose.prod.yml`, `.env.prod.example`,
   and `lothal.conf`. The next two steps create `.env` and install the nginx site from these.

## nginx + TLS (host)

DNS for `lothal.app` already points at `107.172.168.104` (apex + `www`). For a new domain,
point its A/AAAA records at the box first, then:

```bash
DOMAIN=lothal.app                   # the real domain
sudo cp /opt/lothal/lothal.conf /etc/nginx/sites-available/lothal.conf
sudo sed -i "s/__DOMAIN__/$DOMAIN/g" /etc/nginx/sites-available/lothal.conf
# Obtain the cert (cert only; does not rewrite our config):
sudo certbot certonly --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
    --non-interactive --agree-tos -m admin@$DOMAIN
# Enable our site, drop the stock default:
sudo ln -sf /etc/nginx/sites-available/lothal.conf /etc/nginx/sites-enabled/lothal.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

The committed `lothal.conf` uses `listen 443 ssl http2;` (not the newer `http2 on;`) because
Ubuntu 24.04 ships nginx 1.24 — `http2 on;` is 1.25.1+. Renewal is automatic via `certbot.timer`;
test with `sudo certbot renew --dry-run`.

## Create the production .env

The prod config lives **only** on the box at `/opt/lothal/.env` (mode 600) — it is never
committed and never stored in GitHub (see the secrets section for why).

```bash
cd /opt/lothal
cp .env.prod.example .env           # if not already present
# Fill every __CHANGE_ME__. Generate strong values:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # LANGFLOW_SECRET_KEY
#   - POSTGRES_PASSWORD            (compose derives LANGFLOW_DATABASE_URL from POSTGRES_*)
#   - LANGFLOW_SUPERUSER_PASSWORD
#   - LANGFLOW_SECRET_KEY          (generate once — see warning below)
#   - OPENAI_BASE_URL / OPENAI_API_KEY / LOTHAL_MODEL_NAME   (the Epic 0+ LLM interface)
chmod 600 .env
```

> ⚠️ **`LANGFLOW_SECRET_KEY` must stay stable.** It encrypts stored credentials; rotating it
> orphans every encrypted value. Generate it once and never re-render it from CI.

## GHCR auth

- **Automated deploy (C.3):** the GitHub Actions workflow logs into GHCR with the built-in
  `GITHUB_TOKEN` (job `permissions: packages: write`). Because the images live under the same
  owner as the repo (`ghcr.io/realbytecode/lothal-*`), **no PAT secret is required.**
- **Manual pull on the box:** if the images are private, log in once with a PAT that has
  `read:packages`, or publish the packages so the pull needs no auth:
  ```bash
  echo "$GHCR_TOKEN" | docker login ghcr.io -u realbytecode --password-stdin
  ```

## Deploy / redeploy (manual)

```bash
cd /opt/lothal
docker compose -f docker-compose.prod.yml pull
# Run DB migrations before starting the new backend. `migration` (no --fix) applies
# `alembic upgrade head` non-destructively, then verifies. Do NOT pass --fix: it is
# destructive ("delete all data to fix migrations") and interactive (prompts for
# confirmation), so it hangs in CI.
docker compose -f docker-compose.prod.yml run --rm backend python -m langflow migration
docker compose -f docker-compose.prod.yml up -d
# Health check:
curl -fsS https://lothal.app/health && echo " OK"
```

The automated equivalent (build → GHCR → SSH → migrate → up → health-check) is the GitHub
Actions `workflow_dispatch` deploy job (story C.3).

## GitHub Actions secrets (for the C.3 deploy workflow)

Model: **deploy-access only.** GitHub holds the three SSH secrets so CI can reach the box; the
box's `/opt/lothal/.env` remains the single source of prod config, and GHCR auth uses the
workflow's built-in `GITHUB_TOKEN`. This keeps `LANGFLOW_SECRET_KEY` stable and avoids secret
sprawl.

| Secret | Value | Status |
|---|---|---|
| `SSH_HOST` | `107.172.168.104` | ✅ set |
| `SSH_USER` | `lothal` | ✅ set |
| `SSH_KEY` | private half of the deploy ed25519 key (`~/.ssh/lothal_racknerd`) | ✅ set |

Set (or rotate) them with:

```bash
gh secret set SSH_HOST -R realbytecode/langflow --body "107.172.168.104"
gh secret set SSH_USER -R realbytecode/langflow --body "lothal"
gh secret set SSH_KEY  -R realbytecode/langflow < ~/.ssh/lothal_racknerd
gh secret list -R realbytecode/langflow          # confirm
```

**Not stored in GitHub:** `POSTGRES_PASSWORD`, `LANGFLOW_SECRET_KEY`, `LANGFLOW_SUPERUSER_PASSWORD`,
`OPENAI_*`, `LOTHAL_MODEL_NAME`. These live only in `/opt/lothal/.env` on the box. If you later
prefer CI-rendered env, add them as secrets and have C.3 write `.env` — but keep `LANGFLOW_SECRET_KEY`
out of any path that could regenerate it.

**GHCR:** no `GHCR_TOKEN` secret — the C.3 build/push and the on-box pull both use `GITHUB_TOKEN`
(grant the build job `permissions: packages: write`). Only add a PAT if you push images from
outside Actions.

## Verify a fresh bootstrap (C.4 acceptance)

After following the steps above, a fresh box should pass all of:

```bash
# on the server
docker --version                                          # Docker present
systemctl is-enabled certbot.timer                        # -> enabled
ls -l /opt/lothal/{docker-compose.prod.yml,.env,lothal.conf}
test "$(stat -c %a /opt/lothal/.env)" = 600 && echo "env perms OK"
readlink /etc/nginx/sites-enabled/lothal.conf             # -> .../sites-available/lothal.conf
sudo nginx -t                                             # config valid
sudo ls /etc/letsencrypt/live/lothal.app/fullchain.pem    # cert present

# from anywhere, once images exist and the stack is up (C.3):
curl -fsS https://lothal.app/health && echo " OK"         # 200 from the backend via both nginx hops
curl -fsS -o /dev/null -w '%{http_code}\n' https://lothal.app/lothal   # UI route responds
```

The end-to-end "working deploy" needs the GHCR images, which the C.3 workflow builds and pushes;
until C.3 runs, the bootstrap is verified up to "stack starts and `/health` is reachable" using
locally built images (`BACKEND_IMAGE`/`FRONTEND_IMAGE` overrides in `.env`).

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
</content>
</invoke>
