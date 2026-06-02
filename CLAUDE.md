# CLAUDE.md

@AGENTS.md

This project uses [AGENTS.md](https://agents.md/) as the standard for providing context to AI coding agents. The `@AGENTS.md` import above tells Claude Code to load `AGENTS.md` automatically; other tools that natively support `AGENTS.md` will pick it up directly.

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
