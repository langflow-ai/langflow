# lfx-turbo-notify

Turbo Notify WhatsApp messaging components as a standalone Langflow Extension Bundle.

[Turbo Notify](https://turbonotify.com) links an ordinary WhatsApp number to an account as a
linked device and exposes it through a REST API. It is not the Meta WhatsApp Business Platform;
for the Meta Cloud API, use the `lfx-whatsapp` bundle.

The bundle ships six components, all usable in Tool mode:

| Component | Does | Endpoint |
|---|---|---|
| `TurboNotifySendTextComponent` | Text to a phone number, contact or group | `POST /v1/numbers/{ref}/messages` |
| `TurboNotifySendMediaComponent` | Image, video, audio, document or sticker from a public URL | `POST /v1/numbers/{ref}/messages` |
| `TurboNotifyReplyComponent` | Reply to, and quote, an earlier message | `POST /v1/numbers/{ref}/messages/{id}/reply` |
| `TurboNotifyGetMessagesComponent` | Recent messages, filtered by direction, contact or group | `GET /v1/numbers/{ref}/messages` |
| `TurboNotifyGetMessageStatusComponent` | Delivery state of one message | `GET /v1/numbers/{ref}/messages/{id}/status` |
| `TurboNotifyListGroupsComponent` | Groups of the number | `GET /v1/numbers/{ref}/groups` |

The components call the API directly with `httpx` and need only the caller's own API key, so the
bundle adds no dependency beyond `lfx` and `httpx`.

## Install

```bash
pip install lfx-turbo-notify
```

The bundle is registered automatically via the `langflow.extensions` entry-point. After install,
restart your Langflow server; the components appear in the palette's **Bundles** section under
**Turbo Notify**.

## Configure

Set the **Turbo Notify API Key** input to your own key, created in the Turbo Notify dashboard.
**Number** defaults to `main`. **Base URL** is advanced and defaults to `https://api.turbonotify.com`.
The components do nothing until a key is supplied. See the
[Turbo Notify documentation](https://docs.turbonotify.com/en/messages/send/) for the API.

## Develop

```bash
cd src/bundles/turbo-notify
pip install -e .
lfx extension validate src/lfx_turbo_notify
```

## Manifest

The extension manifest is shipped at `src/lfx_turbo_notify/extension.json` and points at the bundle
at `components/turbo_notify`. Components register under namespaced IDs such as
`ext:turbo_notify:TurboNotifySendTextComponent@official`.
