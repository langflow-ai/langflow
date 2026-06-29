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
                        │           │
                        ▼           ▼ (internal /api, no auth — network-isolated)
                 db container    open-design container (OD daemon, :7456,
                 (postgres:16-     internal only — never published)
                  trixie)
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

DNS for `lothal.app` already points at `107.172.168.104` (apex + `www`). **For the
embedded Open Design surface (U.9) you also need an `od.<domain>` A/AAAA record**
pointing at the same box. Point all records at the box first, then:

```bash
DOMAIN=lothal.app                   # the real domain
sudo cp /opt/lothal/lothal.conf /etc/nginx/sites-available/lothal.conf
sudo sed -i "s/__DOMAIN__/$DOMAIN/g" /etc/nginx/sites-available/lothal.conf
# Obtain the cert (cert only; does not rewrite our config). Include od.<domain> so
# the embedded Open Design vhost (U.9) is covered by the same certificate:
sudo certbot certonly --nginx -d "$DOMAIN" -d "www.$DOMAIN" -d "od.$DOMAIN" \
    --non-interactive --agree-tos -m admin@$DOMAIN
# Enable our site, drop the stock default:
sudo ln -sf /etc/nginx/sites-available/lothal.conf /etc/nginx/sites-enabled/lothal.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

> If you don't want the embed yet, omit `-d "od.$DOMAIN"`, leave
> `LOTHAL_OD_PUBLIC_BASE_URL` blank in `.env`, and the prototype pane falls back to
> listing artifacts (no iframe). The `od.<domain>` vhost block stays inert without DNS.

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
#   - CLAUDE_CODE_OAUTH_TOKEN      (Claude Code subscription token — `claude setup-token`; the Epic 0+ LLM interface)
#   - LOTHAL_LLM_PROVIDER / LOTHAL_MODEL_NAME   (optional; default claude / claude-opus-4-8)
#   - OD_IMAGE                     (optional; pin the OD image, e.g. ghcr.io/realbytecode/od:0.11.2 — defaults to :latest)
chmod 600 .env
```

> **Open Design needs no secret.** OD runs internal-only with API auth disabled
> (`OD_DISABLE_API_AUTH=1` in the compose), protected by the private compose network —
> the same posture as `backend:7860`. The only OD key worth setting is `OD_IMAGE`, to
> pin an immutable SHA tag instead of `:latest`. For defense-in-depth, see the
> `OD_API_TOKEN` note in `.env.prod.example`.

> ⚠️ **`LANGFLOW_SECRET_KEY` must stay stable.** It encrypts stored credentials; rotating it
> orphans every encrypted value. Generate it once and never re-render it from CI.

## Access control (invite-only)

The site is **closed**: anonymous visitors only ever see the public landing (`/`), `/login`,
and `/signup` pages — every other route and every `/api/v1/lothal/*` endpoint is auth-gated at
the backend (router-level `get_current_active_user` + per-project owner scoping). Three settings
enforce that nobody can let themselves in, and they are **hardcoded in `docker-compose.prod.yml`**
(literal `"false"`, deliberately not `.env`-overridable, so a fumbled/tampered `.env` cannot
reopen the app):

| Setting | Value | Effect |
|---|---|---|
| `LANGFLOW_AUTO_LOGIN` | `false` | No anonymous superuser session — real credentials required to get in. |
| `LANGFLOW_ENABLE_SIGNUP` | `false` | Public `POST /api/v1/users` returns `403` ("Sign up is currently disabled."). The `/signup` page still renders but submitting it is rejected — no account is created. |
| `LANGFLOW_NEW_USER_IS_ACTIVE` | `false` | New accounts start inactive until the superuser activates them. |

**Provisioning accounts (the only way in):** log in as the superuser
(`LANGFLOW_SUPERUSER` / `LANGFLOW_SUPERUSER_PASSWORD` from `/opt/lothal/.env`) and use the
**`/admin`** page to create users and toggle them active. `ENABLE_SIGNUP=false` blocks public
self-registration but a logged-in superuser can still create users there.

To intentionally open the site later (e.g. enable self-serve signup), flip the relevant value in
`docker-compose.prod.yml` in a reviewed commit and redeploy — not via `.env`.

## GHCR auth

- **Automated deploy (C.3):** the GitHub Actions workflow logs into GHCR with the built-in
  `GITHUB_TOKEN` (job `permissions: packages: write`). Because the images live under the same
  owner as the repo (`ghcr.io/realbytecode/lothal-*`), **no PAT secret is required.**
- **Manual pull on the box:** if the images are private, log in once with a PAT that has
  `read:packages`, or publish the packages so the pull needs no auth:
  ```bash
  echo "$GHCR_TOKEN" | docker login ghcr.io -u realbytecode --password-stdin
  ```
- **Open Design image (cross-repo) — important.** Unlike `lothal-backend`/`lothal-frontend`,
  the OD image (`ghcr.io/realbytecode/od`, built by the `open-design` repo's `docker-image.yml`
  on a `v*.*.*` tag) is published from a **different** repo, so it is a separate GHCR package. The
  C.3 deploy logs in with that run's `GITHUB_TOKEN` (scoped to `realbytecode/langflow`) and then
  runs a blanket `docker compose pull` — which now includes OD. For that pull to succeed, grant the
  langflow repo read access to the OD package **once**: GitHub → the `od` package →
  **Package settings → Manage Actions access → add repository `realbytecode/langflow` (role: Read)**.
  (Equivalently, make the package internal/public.) Note the
  deploy ends with `docker logout ghcr.io`, so a standing PAT login on the box does **not** survive a
  CI deploy — granting package access to the workflow token is the durable fix, not a box-side login.

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
`CLAUDE_CODE_OAUTH_TOKEN`, `LOTHAL_MODEL_NAME`. These live only in `/opt/lothal/.env` on the box. If you later
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

# Open Design data backup (projects + daemon state in /app/.od):
docker run --rm -v lothal_lothal-od-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/od-data-$(date +%F).tgz -C /data .
```

Data lives in named volumes `lothal-db-data` (Postgres), `lothal-langflow-data`
(`/app/langflow`: secret_key, etc.), and `lothal-od-data` (`/app/.od`: OD projects +
daemon state). Don't `docker compose down -v` in production — that deletes them.
(Compose prefixes volume names with the project name `lothal`, so the host volume is
`lothal_lothal-od-data` — see `docker volume ls`.)

## Verify Open Design (U.2 acceptance)

Run from the box after `up -d`. OD is internal-only, so reach it **from the backend
container** over the compose network (proves backend → OD connectivity):

```bash
cd /opt/lothal
# 1. Health endpoint is reachable from the backend over the internal network:
docker compose -f docker-compose.prod.yml exec backend \
  curl -fsS http://open-design:7456/api/health && echo "  -> OD health OK"

# 2. The API answers (auth disabled — no bearer needed on the internal network):
docker compose -f docker-compose.prod.yml exec backend \
  curl -fsS http://open-design:7456/api/projects && echo "  -> OD /api/projects OK"

# 3. Data survives recreation — write a sentinel into the volume, recreate, read it back:
docker compose -f docker-compose.prod.yml exec open-design \
  sh -c 'echo "survived $(date -u +%FT%TZ)" > /app/.od/persistence-check.txt'
docker compose -f docker-compose.prod.yml up -d --force-recreate open-design
docker compose -f docker-compose.prod.yml exec open-design cat /app/.od/persistence-check.txt   # -> survived …
docker compose -f docker-compose.prod.yml exec open-design rm -f /app/.od/persistence-check.txt  # cleanup
```

(If you enable `OD_API_TOKEN` + `OD_DISABLE_API_AUTH=0` for defense-in-depth, step 2 becomes
`curl -H "Authorization: Bearer $OD_API_TOKEN" …` and an unauthed call should `401`.)

## Embed Open Design in the Workspace (U.9)

The prototype pane embeds OD's own project page (its chat, live preview, refine
tools) in an iframe. OD's web app serves everything at the **root** of its origin
(`/api`, `/_next`), so it can't live under a path on `lothal.app` — it gets its own
subdomain, `od.<domain>`, reverse-proxied by host nginx to the OD container and
**gated by the logged-in Lothal session** (nginx `auth_request` → the backend's
`/api/v1/users/whoami`). OD keeps `OD_DISABLE_API_AUTH=1`; the network boundary +
this gate are the access control. Without the gate OD's API would be public and
could spend the LLM subscription, so do not skip it.

**Prerequisites (one-time):**
1. DNS: an `od.<domain>` A/AAAA record at the box, and the cert covering it
   (`-d "od.$DOMAIN"`, see *nginx + TLS* above). The `od.<domain>` vhost is already
   in `lothal.conf`.
2. `.env` on the box:
   ```
   LOTHAL_OD_PUBLIC_BASE_URL=https://od.lothal.app          # browser-facing OD origin → builds the iframe URL
   OD_ALLOWED_ORIGINS=http://open-design:7456,https://od.lothal.app   # OD origin-guard allow-list (backend + browser)
   LANGFLOW_COOKIE_DOMAIN=.lothal.app                       # so the session cookie reaches od.<domain> (rides into the iframe)
   LOTHAL_OD_AGENT_ID=claude                                # must be installed AND available in the OD image (see below)
   ```
   Then `docker compose -f docker-compose.prod.yml up -d` to apply.

**Pick a working agent.** The backend drives one OD agent and points it at the U.3
gateway. It must be *available* in the OD image — list them:
```bash
docker compose -f docker-compose.prod.yml exec backend \
  curl -fsS http://open-design:7456/api/agents | python3 -c \
  'import sys,json;[print(a["id"], a.get("available")) for a in json.load(sys.stdin)["agents"]]'
```
Use one printing `True` (e.g. `claude`). The bare image's historical default
`codex` is frequently **not** available — a mismatch makes runs never start.

**Verify the gate + embed:**
```bash
# Unauthenticated → 401 (gate denies; OD is NOT public):
curl -s -o /dev/null -w "%{http_code}\n" https://od.lothal.app/          # -> 401
# In the browser: log in to https://lothal.app, take a project to the PROTOTYPE
# stage; the right pane embeds https://od.lothal.app/projects/<id> directly — no
# OD sign-in/onboarding prompt — showing the chat history + live preview. Approve
# advances the phase to CODE_GENERATION.
```

> No sign-in prompt because the backend pre-completes OD's onboarding on the daemon
> during seed (`onboardingCompleted` + the agent, via `PUT /api/app-config`). That
> write only succeeds because `ODClient` sends an `Origin` header that is in
> `OD_ALLOWED_ORIGINS` — keep the internal `http://open-design:7456` entry in the
> list or onboarding/agent config silently fails (403) and the embed shows OD's
> sign-in screen.

## LLM gateway: route OD's calls through Lothal (U.3)

Open Design's coding agent makes its own LLM calls. To keep them observable and
centrally controlled, OD's OpenAI-compatible **`codex`** agent is pointed at
Lothal's gateway instead of a provider directly:

```
OD codex agent ──OpenAI /v1/chat/completions──► backend:7860
  /api/v1/lothal/gateway/v1/chat/completions ──► backend chooses one of:
     (default)  SUBSCRIPTION  → translate OpenAI⇄Anthropic, auth via CLAUDE_CODE_OAUTH_TOKEN
     (optional) METERED       → forward verbatim to LOTHAL_GATEWAY_UPSTREAM_* (OpenAI/Anthropic)
```

Tool-calls and streaming work on **both** backends. Pick one:

- **Subscription (default, recommended, no extra cost):** set nothing extra — the
  gateway runs OD's calls on the same `CLAUDE_CODE_OAUTH_TOKEN` the chat provider
  uses, translating OpenAI ⇄ Anthropic Messages under the hood. Point codex's
  model at a **Claude model id**.
- **Metered (override):** set BOTH `LOTHAL_GATEWAY_UPSTREAM_BASE_URL` and
  `LOTHAL_GATEWAY_UPSTREAM_API_KEY` to forward verbatim to an OpenAI-compatible
  upstream on a metered key (takes precedence). Point codex's model at one that
  upstream serves.

> Why not just use OD's native Claude agent? It would talk to Anthropic with its
> own credentials and bypass Lothal entirely. Routing the OpenAI-compatible codex
> agent through this gateway is what makes every call transit (and be logged by)
> Lothal.

### 1. Configure the backend `.env`

In `/opt/lothal/.env` (see `.env.prod.example`). Subscription is automatic once
`CLAUDE_CODE_OAUTH_TOKEN` is set (it already is, for the chat provider). For the
metered override instead:

```bash
LOTHAL_GATEWAY_UPSTREAM_BASE_URL=https://api.openai.com/v1
LOTHAL_GATEWAY_UPSTREAM_API_KEY=<metered-key>
LOTHAL_GATEWAY_TOKEN=$(openssl rand -hex 32)   # optional inbound bearer (recommended)
```

Then `docker compose -f docker-compose.prod.yml up -d backend`. With neither a
subscription token nor a metered upstream, the gateway returns `503`.

### 2. Point OD's codex agent at the gateway (`PATCH /api/app-config`)

OD's `agentCliEnv.codex` carries the agent's OpenAI base URL + key. **The
prototype engine now applies this PATCH automatically** on the first
`POST /prototype/generate` (best-effort — a failed PATCH is logged but does not
abort the run, since OD may already be configured or run on a metered key). The
body it sends is:

```jsonc
// PATCH http://open-design:7456/api/app-config
{
  "agentCliEnv": {
    "codex": {
      "OPENAI_BASE_URL": "http://backend:7860/api/v1/lothal/gateway/v1",
      "OPENAI_API_KEY": "<the same value as LOTHAL_GATEWAY_TOKEN, or any non-empty string if unset>"
    }
  }
}
```

The codex agent's model is then set to one the active backend serves (a **Claude
model id** for the subscription backend). `OPENAI_BASE_URL` ends in `/v1` because
OpenAI clients append `/chat/completions` to it. Override the gateway URL/agent
with `LOTHAL_GATEWAY_PUBLIC_URL` / `LOTHAL_OD_AGENT_ID` (see `.env.prod.example`).

### 3. Verify the gateway (from the backend container)

```bash
cd /opt/lothal
# 503 until a backend is configured; once set, a real completion round-trips and is
# logged on the backend ("lothal gateway (subscription|metered) → model=…"):
docker compose -f docker-compose.prod.yml exec backend sh -c '
  curl -sS -X POST http://localhost:7860/api/v1/lothal/gateway/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $LOTHAL_GATEWAY_TOKEN" \
    -d "{\"model\":\"claude-haiku-4-5\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}"'
docker compose -f docker-compose.prod.yml logs --since=1m backend | grep "lothal gateway"
```

The U.3 acceptance is a full OD prototype run (U.4+) where **every** LLM call shows
up in these gateway logs and the agent's tool loop stays intact (artifacts produced).

## Prototype stage: Lothal drives Open Design (U.4-U.10)

With OD running (U.2) and the gateway configured (U.3), the backend drives OD as a
headless prototyping engine. The flow:

```
ARCHITECTURE approve ─► PROTOTYPE phase (status IDLE)
  POST /api/v1/lothal/projects/{id}/prototype/generate
     → backend builds a brief (PRD + approved architecture), points OD's codex
       agent at the gateway, creates an OD project + starts a run  (status GENERATING)
  GET  …/prototype           → polls status; READY once the OD run succeeds, with artifacts
  POST …/prototype/refine    → a new OD run in the same conversation (a chat-driven tweak)
  POST …/prototype/approve   → copies OD artifacts into lothal_prototype_artifact,
                               status APPROVED, phase → CODE_GENERATION
```

The OD client env (all optional, compose defaults are correct — see
`.env.prod.example` "Prototype stage" block): `LOTHAL_OD_BASE_URL`,
`LOTHAL_OD_API_TOKEN`, `LOTHAL_OD_AGENT_ID`, `LOTHAL_OD_SKILL_ID`,
`LOTHAL_GATEWAY_PUBLIC_URL`, `LOTHAL_OD_PUBLIC_BASE_URL`.

### Embedding the OD web surface (U.9)

The Workspace prototype pane embeds OD's own web UI in an iframe when
`LOTHAL_OD_PUBLIC_BASE_URL` is set to a **browser-reachable** OD URL (the internal
`open-design:7456` is not browser-reachable). Without it, the pane falls back to
listing the produced artifacts. To embed:

1. Expose OD's web on a **separate origin** (a subdomain, e.g. `https://od.lothal.app`)
   proxying `open-design:7456`, and set `LOTHAL_OD_PUBLIC_BASE_URL` to it.
   **Security — do NOT use a same-origin `/od/` path:** the iframe carries
   `allow-scripts allow-same-origin` (OD's app needs both), and those together let a
   *same-origin* frame strip its own sandbox. A separate origin keeps the sandbox
   meaningful. (Cross-origin `allow-same-origin` only grants OD its own origin's
   storage, which it needs — not an escape.)
2. Allow framing: OD must permit `frame-ancestors` for the Lothal origin (and
   Lothal's CSP `frame-src` must allow the OD origin). Configure this in
   `deploy/nginx/lothal.conf` when wiring the OD web subdomain.

> **Status:** U.4-U.8 + U.10 are implemented and unit/integration-tested against a
> mocked OD. U.9's iframe + approve action ship in the pane; the live OD-embed
> round-trip and U.12's real end-to-end smoke require a running OD daemon + Claude
> token and are verified on the deployed stack. U.11 (code generation consuming the
> approved prototype) is **blocked on Epic 4** — there is no code-generation engine
> yet (`GET /code` is still a 501 stub); the approved artifacts already persist in
> `lothal_prototype_artifact`, ready for code-gen to read when it lands.
