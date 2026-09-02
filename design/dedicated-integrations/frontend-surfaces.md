# Frontend surface list for Dedicated Integrations (1.13)

Status: draft
Owners (sign-off roles): frontend owner, release owner
Last verified: 2026-09-01 against `release-1.12.0`

This is the gate's exit criterion "frontend surface list". Every surface is tagged with the ticket that owns it and
whether it is an extension of something that exists or net new. Paths are under `src/frontend/src/`.

## Surfaces that exist and need extension

| # | Surface | Where | Work | Ticket |
|---|---|---|---|---|
| A1 | Settings navigation and route | `pages/SettingsPage/index.tsx` (`sidebarNavItems`), `routes.tsx` (`<Route path="settings">`) | one nav entry `/settings/connections` and one `<Route>`; `settings.nav.connections` in all 7 `src/locales/*.json` | INT-8 |
| A2 | Node header connect button | `CustomNodes/GenericNode/components/NodeStatus/index.tsx` | scans template fields with `type === "auth"`; hard-codes a Composio `api_key`/`COMPOSIO_API_KEY` precondition and a 21 s polling cap; generalize to `connection_ref` state and show "connected as" | INT-8 |
| A3 | In-field connect widget | `components/core/parameterRenderComponent/components/connectionComponent/index.tsx`, `customization/components/custom-connectionComponent.tsx`, dispatch `case "connect"` in `parameterRenderComponent/index.tsx` | keep for Composio; add a sibling `case "connection_ref"` renderer rather than changing `connect` semantics; the 9 s polling cap cannot survive a real consent screen | INT-8 |
| A4 | Action pickers | `sortableListComponent/`, `actionPickerComponent/`, `ListSelectionComponent/` | reuse for per-action selection driven by `search_category`; no change expected | INT-10 to INT-12 |
| A5 | Dynamic field refresh | `CustomNodes/helpers/mutate-template.ts`, `controllers/API/queries/nodes/use-post-template-value.ts`, `use-handle-new-value.ts`, `use-fetch-data-on-mount.ts` | no change; `update_build_config`, `refresh_button`, `real_time_refresh` already work | none |
| A6 | Secret input and global-variable picker | `parameterRenderComponent/components/inputGlobalComponent/`, `components/core/GlobalVariableModal/GlobalVariableModal.tsx` | reuse for API-key-mode connectors; add a read-only "managed by connection" state for fields a connection supersedes | INT-8 |
| A7 | Sidebar catalog | `utils/styleUtils.ts` (`SIDEBAR_CATEGORIES` line 314, `SIDEBAR_BUNDLES` line 418), `pages/FlowPage/components/flowSidebarComponent/components/sidebar-nav-items.ts`, `categoryGroup.tsx` | add `Microsoft 365` and `Slack` bundle groups and fold the existing `Gmail` group into `Google` per `decisions/palette-naming.md` (`GmailLoaderComponent` is re-grouped only); `McpSidebarGroup.tsx` is the template for a group with an empty state and an add modal | INT-11, INT-12 |
| A8 | Icon registry | `icons/lazyIconImports.ts`, `icons/eagerIconImports.ts` | `Gmail`, `GoogleDrive`, `Googlecalendar` exist; add `Microsoft`, `Slack`, `Teams`, `Outlook`, `OneDrive`, `SharePoint` | INT-11, INT-12 |
| A9 | Feature gating | `customization/feature-flags.ts` | `ENABLE_INTEGRATIONS = false` is declared and referenced nowhere; use it, mirrored at runtime through `GET /api/v1/config` like `enable_extension_reload` | INT-8 |
| A10 | OAuth field layout | `modals/authModal/index.tsx` | the richest OAuth form in the codebase, but it configures Langflow as an OAuth *server* (project MCP); harvest layout and the host/port to callback-URL derivation, do not reuse the component | INT-8 |
| A11 | MCP server headers | `modals/addMcpServerModal/index.tsx` (`IOKeyPairInputWithVariables`) | already binds header values to global variables; the path for hand-configured token auth to remote MCP servers stays as is | none |
| A12 | Provider master-detail shell | `modals/modelProviderModal/components/ModelProvidersContent.tsx`, `ProviderList.tsx`, `ProviderListItem.tsx`, `ProviderConfigurationForm.tsx`, `DisconnectWarning.tsx`, `hooks/useProviderConfiguration.ts` | the left-list, right-config layout the Connections page wants; the `validationState` machine and Disconnect warning are reusable; note it writes keys into global variables through `usePostGlobalVariables`, which connections must not do | INT-8 |
| A13 | Account CRUD precedent | `pages/MainPage/pages/deploymentsPage/components/add-provider-modal.tsx`, `provider-credentials-form.tsx`, `providers-table.tsx`, `connection-search-list.tsx`; hooks under `controllers/API/queries/deployment-provider-accounts/` | closest structural analogue for a per-account list and add or edit modal; API-key only, deployment-target scoped | INT-8 |
| A14 | E2E harness | `tests/utils/go-to-settings.ts`, `tests/utils/open-add-mcp-server-modal.ts`, `tests/utils/seed-loopback-provider.ts`, `tests/core/features/composio.spec.ts`, `tests/a11y/*.a11y.spec.ts` with baselines | extend `navigateSettingsPages`; add `connections.a11y.spec.ts` plus baseline; the Composio spec (injects a fake `AuthInput` component, asserts `button_connected_gmail`) is the template for a connector node test | INT-8, INT-14 |

## Surfaces that are net new

| # | Surface | Why nothing exists | Ticket |
|---|---|---|---|
| B1 | `/settings/connections` page: per-user connected accounts with provider, account identity, granted scopes, status, connected-at, reconnect, revoke; operator view of instance connections | no page models a user's third-party account; `GlobalVariablesPage` stores opaque secrets and `ProviderAccount` is deployment-target scoped | INT-8 |
| B2 | Connect-account modal and provider catalog picker (choose provider, see requested scopes, start consent) | `authModal` configures Langflow as an OAuth server, not as a client | INT-8 |
| B3 | OAuth return handling: popup with an origin-checked `postMessage` or a callback route with a `window.closed` watchdog and blocked-popup fallback; the Desktop loopback case on `localhost:7860` | the only mechanism today is `customOpenNewTab` plus `mutateTemplate` polling capped at 21 s; no `/oauth/callback` route, no `postMessage` OAuth (all `postMessage` hits are AudioWorklet in `voice-assistant/`) | INT-8 |
| B4 | Connections Zustand store and `controllers/API/queries/connections/` (`useGetConnections`, `usePostConnection`, `useDeleteConnection`, `useTestConnection`) with cache invalidation on connect | `src/stores/` has no connection store; the only `connection` matches in `flowStore.ts` are ReactFlow edges | INT-8 |
| B5 | Per-field connection status: "connected as", scope-missing warning against `required_scopes`, expired-token re-auth call to action keyed on the typed error `code` | fields express only `validated`, `error`, or a URL; no identity, scope, or expiry surface | INT-8 |
| B6 | Token-expiry and re-consent notification through `alertStore` | no expiry concept exists; nothing feeds token lifecycle events | INT-8 |
| B7 | Connection choice per node when a user has two accounts for one provider | global variables have `PermissionsProvider` sharing but no account-selection-per-node concept | INT-8 |
| B8 | Connectors sidebar section with live connection state (grey out unconnected providers, inline connect) | `SIDEBAR_BUNDLES` entries are static records with no runtime binding; `extension_id` is not populated, which is also why bundle reload is flagged off | INT-8 (MVP: none; defer to 1.14) |

## Constraints the design must record

1. The connect flow today is new-tab-plus-polling with 21 s and 9 s caps. A real Google or Microsoft consent screen
   (account chooser, scope grant, possible MFA) routinely exceeds both. Either B3 is built or the polling budget and
   its timed-out state are redesigned; silently reverting to disconnected after 9 s reads as a bug.
2. Every credential today lands in the global-variables table (`ModelProvidersPage`, `DBProvidersPage`, and the
   node-level secret picker all write through `usePostGlobalVariables`). Connections get their own store (B4) and
   must not appear in `/settings/global-variables`; the design says so explicitly so users do not see unexplained
   rows and so existing sharing tooling is not assumed to cover them.
3. Desktop (Tauri) runs the backend on `localhost:7860`, so the OAuth return is the same callback route as
   self-managed with a public client and loopback redirect; the frontend needs no Tauri-specific bridge for the
   return, only for opening the system browser. Slack's MCP server documents PKCE for desktop clients, and enabling
   PKCE marks the Slack app a public client, one-way, so Desktop Slack uses a customer-owned, PKCE-enabled app
   registration (`decisions/substrate-slack.md` fact 9).
4. A11y is a review gate here: every settings page ships an axe baseline spec, and `NodeStatus`,
   `GlobalVariablesPage`, and `MCPServersPage` carry explicit WCAG comments. B1, B2, and B5 need keyboard-only paths.

## MVP versus defer

MVP for 1.13: A1, A2, A3 (sibling renderer), A6, A7, A8, A9, A12 (layout reuse), A14, B1, B2, B3, B4, B5.
Defer: B6 (surface expiry only through B5 at first), B7 (one connection per provider per user in wave 1; a second
account becomes a second named connection selectable in the picker), B8.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| frontend owner | | | |
| release owner | Eric Hare | 2026-09-01 | #14906 (confirmed in the planning session) |
