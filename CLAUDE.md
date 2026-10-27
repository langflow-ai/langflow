# CLAUDE.md

@AGENTS.md
@.claude/CLAUDE.md

This project uses [AGENTS.md](https://agents.md/) as the standard for providing context to AI coding agents. The `@AGENTS.md` import above tells Claude Code to load `AGENTS.md` automatically; other tools that natively support `AGENTS.md` will pick it up directly. The `@.claude/CLAUDE.md` import loads the local hard-rules file (gitignored) that mirrors the PostToolUse hook policy.

## Documentation

Write feature notes in `docs/features/`. That folder is not published.

User-facing pages live in `docs/docs/` and `docs/versioned_docs/`, with navigation in `docs/sidebars.js`. Edit those only when the task is a user-facing docs change the docs writer should review. A pull request that touches `docs/` flags the docs team. That notice is optional and does not block merge.

Released model docs are generated at version cut and committed under `docs/static/llms.txt` and `docs/static/llms/<version>/`. Leave those files unchanged.
