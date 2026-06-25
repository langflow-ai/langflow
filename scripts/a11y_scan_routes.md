# Langflow Accessibility Scan Route Map

This file lists frontend routes/pages that can be targeted by `scripts/a11y_scan.py`.

Sources inspected:

- `src/frontend/src/routes.tsx`
- `src/frontend/src/customization/utils/custom-routes-store.tsx`
- `src/frontend/src/customization/utils/custom-routes-store-pages.tsx`
- `src/frontend/src/customization/feature-flags.ts`
- `src/frontend/src/customization/config-constants.ts`

Current static route assumptions:

- `BASENAME` is empty, so route paths below start at `/`.
- `ENABLE_CUSTOM_PARAM` is `false`, so tenant/custom-prefix variants are not active.
- `ENABLE_FILE_MANAGEMENT` is `true`, so `/assets` routes are active.
- `ENABLE_KNOWLEDGE_BASES` is `true`, so knowledge-base routes are active.

## Scan-Ready Static Pages

These routes do not need IDs. Some may still redirect depending on auth, store, or user role.

| Route | Page / behavior | Notes |
| --- | --- | --- |
| `/` | Dashboard index | Redirects to `/flows`. Useful smoke route. |
| `/flows` | Home page, flows tab | Primary flows list. |
| `/components` | Home page, components tab | Components list. |
| `/all` | Home page, all/flows tab | Used by app navigation after some actions. |
| `/mcp` | Home page, MCP tab | MCP list. |
| `/assets` | Assets index | Redirects to `/assets/files`. |
| `/assets/files` | Files page | File management route. |
| `/assets/knowledge-bases` | Knowledge bases page | Requires knowledge-base feature flag. |
| `/settings` | Settings index | Redirects to `/settings/general`. |
| `/settings/general` | General settings page | May redirect to `/settings/global-variables` when the settings guard hides general settings. |
| `/settings/general/api` | General settings with `scrollId=api` | Route matches `:scrollId`; observed navigation target. |
| `/settings/global-variables` | Global variables settings page | Good modal-state candidate, but base page is scan-ready. |
| `/settings/model-providers` | Model providers settings page | Static settings page. |
| `/settings/db-providers` | DB providers settings page | Static settings page. |
| `/settings/mcp-servers` | MCP servers settings page | Static settings page. |
| `/settings/mcp-client` | MCP client settings page | Static settings page. |
| `/settings/api-keys` | API keys settings page | Static settings page. |
| `/settings/shortcuts` | Shortcuts settings page | Static settings page. |
| `/settings/messages` | Messages settings page | Static settings page. |
| `/settings/store` | Store API key settings page | Route exists through custom store routes. |
| `/account/delete` | Delete account page | Protected account page. |
| `/admin` | Admin page | Requires admin access; otherwise redirects. |
| `/login` | Login page | Login guard redirects authenticated users. |
| `/signup` | Sign-up page | Login guard redirects authenticated users. |
| `/login/admin` | Admin login page | Login guard redirects authenticated users. |
| `/store` | Store page | Store guard may redirect to `/all` when store is unavailable. |

## Dynamic Pages Requiring IDs

These routes are valid scan targets only after replacing placeholders with real IDs from app/API data.

| Route template | Page / behavior | Needed value |
| --- | --- | --- |
| `/components/folder/:folderId` | Components tab filtered by folder | Folder ID. |
| `/all/folder/:folderId` | All/flows tab filtered by folder | Folder ID. |
| `/mcp/folder/:folderId` | MCP tab filtered by folder | Folder ID. |
| `/assets/knowledge-bases/:sourceId/chunks` | Knowledge-base source chunks page | Knowledge-base source ID. |
| `/flow/:id/` | Flow editor page | Flow ID. |
| `/flow/:id/folder/:folderId/` | Flow editor page scoped from folder route | Flow ID and folder ID. |
| `/flow/:id/view` | Flow view page | Flow ID. |
| `/playground/:id/` | Shared playground page | Flow/share ID. |
| `/store/:id/` | Store detail page | Store item ID. |

## Redirect / Fallback Routes

These are useful to understand scanner output but are not unique page surfaces.

| Route | Behavior |
| --- | --- |
| `/` | Redirects to `/flows`. |
| `/assets` | Redirects to `/assets/files`. |
| `/settings` | Redirects to `/settings/general`. |
| `*` | Redirects to `/`. |

## Conditional Route Variants

If `ENABLE_CUSTOM_PARAM` becomes `true`, the main protected route tree is mounted under `/:customParam?`.

Examples:

- `/{customParam}/flows`
- `/{customParam}/assets/files`
- `/{customParam}/settings/general`
- `/{customParam}/flow/:id/`

This flag is currently `false`, so do not include these prefixed variants in normal scan batches.

## Suggested Full Static Scan Batch

Use this when the frontend is running and authenticated as a user with broad access:

```bash
uv run python scripts/a11y_scan.py \
  --url http://localhost:3000 \
  --routes /,/flows,/components,/all,/mcp,/assets,/assets/files,/assets/knowledge-bases,/settings,/settings/general,/settings/general/api,/settings/global-variables,/settings/model-providers,/settings/db-providers,/settings/mcp-servers,/settings/mcp-client,/settings/api-keys,/settings/shortcuts,/settings/messages,/settings/store,/account/delete,/admin,/login,/signup,/login/admin,/store \
  --out /tmp/langflow-a11y-all-static.json \
  --markdown /tmp/langflow-a11y-all-static.md \
  --html /tmp/langflow-a11y-all-static.html \
  --timeout-ms 45000
```

## Dynamic Scan Notes

Dynamic routes should be scanned after collecting real IDs:

- `folderId`: from loaded folder data or folder API responses.
- `sourceId`: from knowledge-base/source API responses.
- `flow id`: from the flows list/API.
- `store item id`: from store API responses.

Do not scan placeholder URLs like `/flow/:id/`; they will not represent a real page state.
