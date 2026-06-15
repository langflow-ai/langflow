# CLAUDE.md

@AGENTS.md

This project uses [AGENTS.md](https://agents.md/) as the standard for providing context to AI coding agents. The `@AGENTS.md` import above tells Claude Code to load `AGENTS.md` automatically; other tools that natively support `AGENTS.md` will pick it up directly.

## Branching

`main` is kept **static** — it mirrors the upstream Langflow release (currently the `1.9.5` tag) and is only ever advanced to track a new upstream version. **Do all development on `dev`.** Create every worktree and feature branch from `dev`, never from `main`.

## Dev Containers (wt.sh)

Always use `scripts/wt.sh` to manage dev containers — never raw docker commands.

```bash
./scripts/wt.sh up      # start container for current context
./scripts/wt.sh down    # stop container
./scripts/wt.sh logs    # follow logs
./scripts/wt.sh status  # show all running langflow containers
./scripts/wt.sh config  # print this context's saved config
```

- **Main repo** → proxies to `docker/dev.docker-compose.yml` (standard dev container on ports 7860/3000)
- **Worktree** → on first `up`, generates `.wt-config` at the worktree root with auto-assigned ports and an isolated DB; reuses that config on every subsequent call

`.wt-config` is gitignored and machine-specific. The Postgres container from the main dev stack must be running before starting any worktree container.

## Lothal product conventions

- **Terminology — no "dockyard"/nautical wording.** Do **not** introduce new dockyard/harbor/vessel/drydock/"workshop"/"ship it" terminology in Lothal UI copy, component names, or comments. The product name **Lothal** stays. Existing nautical terminology (e.g. "No vessels in the harbor", `HarborWatermark`, "Sign in to your dockyard") is being phased out in a **future, dedicated change** — leave it untouched until that task; just don't add more.
- **Post-login destination is the Lothal projects page (`/lothal`).** The funnel is **landing (`/`) → login (`/login`) → projects (`/lothal`)**. The Lothal login page defaults its own post-login redirect to `/lothal` (via `setRedirectUrl` when there's no explicit `?redirect`); the shared `ProtectedLoginRoute` still falls back to `/flows` for non-Lothal flows (e.g. `/login/admin`), which is intentional.
