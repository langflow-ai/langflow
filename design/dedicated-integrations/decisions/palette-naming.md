# Palette naming and sidebar grouping for native connectors next to Composio components

Status: proposed
Decision ID: palette-naming
Applies to: display names and component classes in matrices/*.json; SIDEBAR_BUNDLES in src/frontend/src/utils/styleUtils.ts; INT-10, INT-11, INT-12
Owners (sign-off roles): frontend owner, product owner, release owner
Last verified: 2026-09-01

## Context

Composio wrappers for the same products already exist in the opt-in `lfx-bundles` metapackage, and the Google
bundle already ships loader components. Users who install `langflow[bundles]` will see both families. This record
fixes display names, class names, and sidebar groups before INT-10 to INT-12 create classes, because bare class
names must be unique across bundles and the migration table is append-only.

## Facts (with citations)

| # | Fact | Source | Verified on | Confidence |
|---|------|--------|-------------|------------|
| 1 | Composio components use bare product nouns as display names: `ComposioGmailAPIComponent` "Gmail", `ComposioOutlookAPIComponent` "Outlook", `ComposioSlackAPIComponent` "Slack", `ComposioSlackbotAPIComponent` "Slackbot" | `src/bundles/lfx-bundles/src/lfx_bundles/composio/{gmail,outlook,slack,slackbot}_composio.py:5` | 2026-09-01 | high |
| 2 | The Google bundle ships `GmailLoaderComponent` "Gmail Loader", `GoogleDriveComponent` "Google Drive Loader", `GoogleDriveSearchComponent` "Google Drive Search", and `GoogleOAuthToken` "Google OAuth Token" (`legacy = True`) | `src/bundles/google/src/lfx_google/components/google/*.py` | 2026-09-01 | high |
| 3 | `SIDEBAR_BUNDLES` already has separate `Gmail` (line 467) and `Google` (line 468) groups, a `Composio` group (line 451), and an `Azure` group (line 441); there is no `Microsoft` or `Slack` group | `src/frontend/src/utils/styleUtils.ts` | 2026-09-01 | high |
| 4 | `migration_table.json` carries rows for `GmailLoaderComponent`, `GoogleDriveComponent`, `GoogleOAuthToken`, and `ComposioGmailAPIComponent`; bare names must stay unique and the table is append-only | `src/lfx/src/lfx/extension/migration/migration_table.json`, `scripts/migrate/check_bare_names.py`, `check_migration_append_only.py` | 2026-09-01 | high |
| 5 | Composio components are not in the default install (the `lfx-bundles` metapackage is opt-in in 1.12) | `src/bundles/lfx-bundles/pyproject.toml`; release notes | 2026-09-01 | high |

## Options

### Option A: Rename Composio components to "<Product> (Composio)"

Pros: bare product names free for native components. Cons: changes a shipped bundle's display names (saved flows
keep working because class names are unchanged, but search and documentation churn); the plan's rule is that
Composio components are not silently reclassified.

### Option B: Native components use "Product: Verb Object"; Composio names unchanged; new provider groups (recommended)

Native display names carry the product and the action, for example "Gmail: Send Email", "Outlook: Send Mail",
"Slack: Post Message (as app)", exactly as the matrices already record. Composio keeps "Gmail", "Outlook", "Slack",
"Slackbot" under the `Composio` sidebar group. Search for "Gmail" returns both, distinguishable by label and group.
Class names are product-prefixed (`GmailSendComponent`, `OutlookSendComponent`, `SlackPostAsAppComponent`) and never
collide with existing bare names (fact 4).

### Option C: One "Connectors" category for all native provider actions

Pros: a single discoverable home. Cons: cuts across the bundle-per-provider packaging; the sidebar already groups by
bundle, and a cross-bundle category needs runtime binding the sidebar does not have (`frontend-surfaces.md` B8).

## Decision

Option B, with these sidebar rules:

1. Native Google actions join the existing `Google` group. The `Gmail` group (which today exists only for the Gmail
   loader) is folded into `Google` in INT-10; `GmailLoaderComponent` keeps its class name and display name and is
   re-grouped only. `GoogleOAuthToken` is hidden from the palette when connections land, per INT-10.
2. New `Microsoft 365` group (icon `Microsoft`) for `lfx-microsoft`, kept separate from the existing `Azure` group,
   which holds the Azure OpenAI model components.
3. New `Slack` group (icon `Slack`) for `lfx-slack`; the two Composio Slack components stay under `Composio`.
4. Display names follow "Product: Verb Object", with "(as user)" or "(as app)" suffixes only where one product has
   both identities (Slack).
5. Class names are `<Product><Verb><Object>Component` and are checked against the migration table's bare names
   before INT-10 to INT-12 open.

## Consequences

- `SIDEBAR_BUNDLES` gains two entries and loses one; the icon registry gains `Microsoft`, `Slack`, `Teams`,
  `Outlook`, `OneDrive`, `SharePoint` (see `frontend-surfaces.md` A7, A8).
- Documentation pages `bundles-microsoft.mdx` and `bundles-slack.mdx` name the groups the same way.
- No Composio file changes.

## Re-open trigger

- Composio components join the default install, or
- the sidebar gains runtime bundle binding (B8), which would make a cross-provider "Connectors" view cheap.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| frontend owner | | | |
| product owner | | | |
| release owner | | | |
