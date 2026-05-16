# lfx-google-workspace

Google Workspace integrations: Gmail loader, Drive loader/search, and OAuth token helper.

Part of the Google split (4-way separation of the legacy `lfx.components.google` directory).

## Components

| Class | Module |
| --- | --- |
| `GmailLoaderComponent` | `gmail` |
| `GoogleDriveComponent` | `google_drive` |
| `GoogleDriveSearchComponent` | `google_drive_search` |
| `GoogleOAuthToken` | `google_oauth_token` |

## Install

```bash
pip install lfx-google-workspace
```

## Develop

```bash
cd src/bundles/google_workspace
pip install -e .
lfx extension validate src/lfx_google_workspace
```

## Migration

Saved flows that referenced `lfx.components.google.*` for one of this bundle's components rewrite to `ext:google_workspace:<Class>@official` via the migration table at `src/lfx/src/lfx/extension/migration/migration_table.json`.
