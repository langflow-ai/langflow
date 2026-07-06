# IBM Accessibility Level 1 — Route Validation Tracker

> Companion to the criteria guide: [ibm-a11y-level1-criteria.md](ibm-a11y-level1-criteria.md)
> Scope: Langflow frontend (`src/frontend/src`). Standard: IBM Equal Access Toolkit v7.3 — Level 1.

This is a **manual validation tracker**. Each route below owns one checkbox. Tick a box only when that route has been manually confirmed to pass IBM Level 1 per [ibm-a11y-level1-criteria.md](ibm-a11y-level1-criteria.md).

### Checkbox legend

- `- [ ]` — not yet validated
- `- [x]` — validated for IBM Level 1

---

## Static routes

- [ ] `/flows` — Home / flows list
- [ ] `/all` — Home / all list
- [ ] `/components` — Home / components list
- [ ] `/components/folder/:folderId` — Components (folder)
- [ ] `/all/folder/:folderId` — All (folder)
- [ ] `/mcp` — Home / MCP list
- [ ] `/mcp/folder/:folderId` — MCP (folder)
- [ ] `/assets/files` — Files page
- [ ] `/assets/knowledge-bases` — Knowledge bases page
- [ ] `/settings` — Settings shell
- [ ] `/settings/general` — General settings
- [ ] `/settings/global-variables` — Global variables
- [ ] `/settings/model-providers` — Model providers
- [ ] `/settings/db-providers` — DB providers
- [ ] `/settings/mcp-servers` — MCP servers
- [ ] `/settings/mcp-client` — MCP client
- [ ] `/settings/api-keys` — API keys
- [ ] `/settings/shortcuts` — Shortcuts
- [ ] `/settings/messages` — Messages
- [ ] `/settings/store` — Store API key
- [ ] `/account/delete` — Delete account

## Dynamic routes

- [ ] `/flow/:id/` — Flow editor (canvas)
- [ ] `/flow/:id/folder/:folderId/` — Flow editor (folder)
- [ ] `/flow/:id/view` — Flow view (read-only canvas)
- [ ] `/playground/:id/` — Shared playground
- [ ] `/assets/knowledge-bases/:sourceId/chunks` — KB source chunks

## Gated routes (auth/role/environment specific)

- [ ] `/login` — Login
- [ ] `/signup` — Sign up
- [ ] `/login/admin` — Admin login
- [ ] `/admin` — Admin page
- [ ] `/store` — Store
- [ ] `/store/:id/` — Store item detail
