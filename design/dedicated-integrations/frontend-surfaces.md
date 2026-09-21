# Frontend surface list for Dedicated Integrations (1.13)

Status: draft
Owners (sign-off roles): frontend owner, release owner
Last verified: 2026-09-01 against `release-1.12.0`; requirements amended 2026-09-09
Last amended: 2026-09-10 (interim trigger consent ownership)

This is the gate's exit criterion "frontend surface list". Every surface is tagged with the ticket that owns it and
whether it is an extension of something that exists or net new. Paths are under `src/frontend/src/`.

INT-8's B1 owns the permanent per-connection "Allow background runs" control. Before that page ships, TRG-7 owns
the interim control and missing-consent recovery (`../dedicated-integrations-triggers/frontend-surfaces.md` B9).
The permission applies to all eligible background uses of the connection, not just the selected trigger. Both
surfaces require INT-4's connection-owner-only update API, which still needs to be added to its current PR; selecting
an account or completing OAuth never grants this local permission implicitly.

## Surfaces that exist and need extension

| # | Surface | Where | Work | Ticket |
|---|---|---|---|---|
| A1 | Settings navigation and route | `pages/SettingsPage/index.tsx` (`sidebarNavItems`), `routes.tsx` (`<Route path="settings">`) | one nav entry `/settings/connections` and one `<Route>`; `settings.nav.connections` in all 7 `src/locales/*.json` | INT-8 |
| A2 | Node header connect button | `CustomNodes/GenericNode/components/NodeStatus/index.tsx` | scans template fields with `type === "auth"`; hard-codes a Composio `api_key`/`COMPOSIO_API_KEY` precondition and a 21 s polling cap; generalize to `connection_ref` state and show "connected as" | INT-8 |
| A3 | In-field connect widget | `components/core/parameterRenderComponent/components/connectionComponent/index.tsx`, `customization/components/custom-connectionComponent.tsx`, dispatch `case "connect"` in `parameterRenderComponent/index.tsx` | keep for Composio; add a sibling `case "connection_ref"` renderer rather than changing `connect` semantics; the 9 s polling cap cannot survive a real consent screen | INT-8 |
| A4 | Action pickers | `sortableListComponent/`, `actionPickerComponent/`, `ListSelectionComponent/` | reuse for per-action selection driven by `search_category`; label each action with its executing identity (B5), including user versus app, before selection | INT-10 to INT-12 |
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
| B1 | `/settings/connections` page: per-user connected accounts with provider, account identity, granted scopes, status, connected-at, reconnect, revoke; persisted `allow_non_interactive` toggle (default off), visible enabled badge, explanation and disable control; operator view of instance connections | no page models a user's third-party account; `GlobalVariablesPage` stores opaque secrets and `ProviderAccount` is deployment-target scoped | INT-8 |
| B2 | Connect-account modal and provider catalog picker (choose provider and actions; explain each action's purpose, executing identity, existing/new scopes and effective reach before starting consent, including private channels/DMs for Slack reads) | `authModal` configures Langflow as an OAuth server, not as a client | INT-8 |
| B3 | OAuth return handling: popup with an origin-checked `postMessage` or a callback route with a `window.closed` watchdog and blocked-popup fallback; the Desktop loopback case on `localhost:7860` | the only mechanism today is `customOpenNewTab` plus `mutateTemplate` polling capped at 21 s; no `/oauth/callback` route, no `postMessage` OAuth (all `postMessage` hits are AudioWorklet in `voice-assistant/`) | INT-8 |
| B4 | Connections Zustand store and `controllers/API/queries/connections/` (`useGetConnections`, `usePostConnection`, `usePatchConnection`, `useDeleteConnection`, `useTestConnection`) with cache invalidation on connect | `src/stores/` has no connection store; the only `connection` matches in `flowStore.ts` are ReactFlow edges | INT-8 |
| B5 | Per-field connection status and action identity: "connected as" plus "runs as user {account}" or "runs as app {app}" from the selected capability and connection; show in the action picker, selected node and pre-run summary, with updates on action/account changes; scope-missing warning against `required_scopes`, expired-token re-auth call to action keyed on the typed error `code` | fields express only `validated`, `error`, or a URL; no identity, scope, or expiry surface | INT-8 |
| B6 | Token-expiry and re-consent notification through `alertStore` | no expiry concept exists; nothing feeds token lifecycle events | INT-8 |
| B7 | Connection choice per node when a user has two accounts for one provider | global variables have `PermissionsProvider` sharing but no account-selection-per-node concept | INT-8 |
| B8 | Connectors sidebar section with live connection state (grey out unconnected providers, inline connect) | `SIDEBAR_BUNDLES` entries are static records with no runtime binding; `extension_id` is not populated, which is also why bundle reload is flagged off | INT-8 (MVP: none; defer to 1.14) |
| B9 | Operator integration-policy panel within `/settings/connections`: provider enable/disable, allowed capability ids, allowed connection owner kinds, and hosted-registration readiness; hidden from non-operators and backed by the governance service rather than frontend-only flags | no current settings surface exposes provider/capability policy; the model-provider policy precedent is API and plugin wiring, not a reusable integration-policy UI | INT-7 |
| B10 | Non-interactive publication preflight for deployments and project MCP with auth `none`: list each required connection and its executing identity, display opt-in state and exposure warning, block publication if runtime authorization would deny access, link an authorized owner to B1; webhook setup uses the same preflight when that deferred track ships | publication has no per-connection permission review today | INT-8 presentation; INT-4/6 enforce and expose authorization outcome |
| B11 | Builder policy/unavailable-action state in catalog, picker, imported node and run/publish errors: a disabled action has an accessible explanation and next step; an existing node remains intact | B9 is operator-only and cannot explain a deny to the builder | INT-8 presentation; INT-7 sanitized effective-policy/deny contract; INT-3 unavailable capability metadata |
| B12 | Tenant approval required, denied, or indeterminate state in connect/return and connection details: explain provider admin approval, preserve the pending connection context and offer retry after approval; distinguish tenant approval from Langflow policy and user cancellation | provider consent defaults do not establish a customer's actual consent policy | INT-5 error mapping; INT-8 presentation; INT-14 tenant validation |
| B13 | Google Picker authorization entry point for `drive.file`; future file-selection UI must use the same connection/app registration and show the effective file boundary | no Picker exists and an arbitrary file-id input cannot grant the app access | deferred to 1.14; INT-8 UI and INT-10 provider integration must be sized before re-opening |
| B14 | Drive list empty state and fetch access limitation in node help/output, connection details and the KB connector picker: explain app-authorized files and that full-Drive access/Picker are unavailable in wave 1 | `drive.file` can legitimately return no files on a new connection, which currently looks like a broken list action | INT-8 owns shared rendering/copy; INT-10 supplies the capability limitation and empty/access outcome; INT-14 acceptance tests |

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
   return, only for opening the system browser. Desktop defaults to Langflow-owned public clients, so the connect
   flow has no registration step; the customer-owned registration form is the one self-managed uses and is the
   override (`decisions/desktop-oauth-ownership.md`). Slack's PKCE opt-in marks the app a public client, one-way,
   so Desktop Slack uses a second, Langflow-owned, PKCE-enabled Slack app (`decisions/substrate-slack.md` fact 9).
4. A11y is a review gate here: every settings page ships an axe baseline spec, and `NodeStatus`,
   `GlobalVariablesPage`, and `MCPServersPage` carry explicit WCAG comments. B1, B2, and B5 need keyboard-only paths.
5. B9 is an operator control, not a substitute for backend enforcement. The API returns effective policy and rejects
   forbidden provider, capability, owner-kind, and registration-mode combinations; hiding a control in React is
   only presentation. B11 must render the same sanitized outcome for non-operators; a hidden operator panel is not remediation.

## Required UX behavior and acceptance checks

- **Non-interactive use (B1/B10):** the toggle persists through the connection API and is off by default. Explain:
  "Allow this connection to be used by deployments and other supported non-interactive runs acting as its owner."
  Enabling requires a deliberate acknowledgement of the acting identity and callers; changing it never enables
  anonymous public access or bypasses policy. Show state set through the API too. On disable, subsequent credential
  resolutions fail as specified by the contract. Publication says which connection prevents the run and directs
  its authorized owner to settings; never auto-enables it. Public MCP with auth `none` explicitly warns that callers
  invoke the owner's identity. The runtime guard remains authoritative after publish.
- **Scope rationale (B2):** INT-10/11/12 bundle owners author purpose, scope breadth and identity; INT-8 owns the
  localized presentation and consent transition; product/frontend owners approve copy. Before Slack thread consent:
  "This connection can read public channels, private channels you belong to, direct messages and group direct
  messages. The permission covers more than the thread selected in this node." Search gets its own workspace-wide
  explanation. Show prior grants and new grants, and allow cancellation before opening the provider screen.
- **Identity (A4/B5):** `slack.user.send` says it posts as the connected user; `slack.bot.post` says it posts as the
  installed app. Account and capability changes refresh the label; a mismatched profile cannot run. Never infer
  executing identity from the account name alone.
- **Policy (B11):** show "Your organization has disabled this integration/action. Contact your administrator."
  For unsupported deployment contexts show "This action is unavailable in this deployment." Use typed
  `connection-not-authorized` / `action-unsupported` outcomes and safe hints, without exposing other users'
  connections or hidden policy configuration. Also handle a policy change after the picker was opened.
- **Tenant consent (B12):** `consent: user` is a provider default. Show "Your administrator must approve this app
  and its requested permissions" only for a recognized provider outcome; ambiguous denial says consent could not
  complete and suggests checking with the administrator. Never infer approval from elapsed time, loop reconnects
  on a permanent denial, or mark a connection ready before the provider flow succeeds. INT-14 validates allowed,
  approval-required and blocked cases using the actual tenant and registration before rollout.
- **Drive (B14):** on a successful empty list show "No files are available to this connection. Langflow can access
  only files created by or explicitly opened/selected for this app. Connecting your account does not grant access
  to all Drive files. File selection with Google Picker is not available in this release." Do not offer a working
  Picker button or claim a file-id input grants access. A fetch outside the grant explains the same limitation;
  it must not silently broaden scopes. Preserve the empty result for flow execution and show the explanation in
  help/output UI; an API failure remains an error. Include this copy in the KB connector picker/help too.
- **Validation owners:** INT-8 covers keyboard navigation, accessible warnings, i18n and persisted toggle state;
  INT-10/11/12 cover metadata and normalized provider outcomes; INT-14 covers the end-to-end scenarios above,
  including import of unavailable nodes as defined in `cross-provider-capabilities.md`.

## MVP versus defer

MVP for 1.13: A1, A2, A3 (sibling renderer), A4 (identity labels), A6, A7, A8, A9, A12 (layout reuse), A14, B1, B2, B3, B4, B5, B9, B10 (deployment/MCP), B11, B12, B14.
Defer: B6 (surface expiry only through B5 at first), B7 (one connection per provider per user in wave 1; a second
account becomes a second named connection selectable in the picker), B8, B13 (Google Picker), and webhook setup in B10 until the trigger track ships.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| frontend owner | | | |
| release owner | Eric Hare | 2026-09-01 | #14906 (confirmed in the planning session) |
