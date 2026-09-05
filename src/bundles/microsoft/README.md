# lfx-microsoft

Microsoft 365 and Teams actions for Langflow, backed by **delegated** Microsoft Graph
v1.0 permissions. Application (app-only) permissions are deliberately excluded.

## Install

```bash
uv pip install lfx-microsoft
```

The bundle is part of the default `langflow` install; install it directly only when
you installed `lfx` on its own.

## Components

| Component | Capability | Delegated permissions |
| --- | --- | --- |
| Outlook: Send Mail | `microsoft.outlook.send` | `Mail.Send` |
| Outlook: Search Mail | `microsoft.outlook.search` | `Mail.Read` |
| Outlook Calendar: List Events | `microsoft.calendar.list` | `Calendars.Read` |
| Outlook Calendar: Create Event | `microsoft.calendar.create` | `Calendars.ReadWrite` |
| Teams: Post Chat Message | `microsoft.teams.chat_post` | `ChatMessage.Send` |
| Teams: Post Channel Message | `microsoft.teams.channel_post` | `ChannelMessage.Send` |
| SharePoint/OneDrive: List Items | `microsoft.files.list` | `Files.Read` (+ `Files.Read.All` with a drive id, `Sites.Read.All` with a site id) |
| SharePoint/OneDrive: Fetch Item | `microsoft.files.fetch` | `Files.Read` (+ `Files.Read.All` with a drive id, `Sites.Read.All` with a site id) |

`offline_access` is requested by the OAuth registration, not by an action: Microsoft
Entra never echoes it in the token response, so it must stay out of the per-action
required scopes.

Every component takes a portable connection handle (`microsoft/<name>`) and resolves it
through the host's connection resolver. See
[Configure connection OAuth](https://docs.langflow.org/connection-oauth) and
[Register a Microsoft Entra application](https://docs.langflow.org/entra-app-registration).
