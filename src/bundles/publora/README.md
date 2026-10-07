# lfx-publora

Publora social media publishing components as a standalone Langflow Extension Bundle.

[Publora](https://publora.com) publishes and schedules posts to LinkedIn, X,
Instagram, Threads, TikTok, YouTube, Facebook, Bluesky, Mastodon and Telegram.
The bundle ships two components that call the
[Publora REST API](https://docs.publora.com) directly with `httpx` and need
only a user-supplied API key, so it carries no vendor SDK dependency:

- `PubloraListConnectionsComponent` lists the social accounts connected to the
  Publora account, with the `platformId` each post is addressed to.
- `PubloraCreatePostComponent` creates a post for one or more `platformId`
  values. Without a scheduled time the post is saved as a draft and is never
  published; with an ISO 8601 UTC time it is scheduled.

## Install

```bash
pip install lfx-publora
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; both components
appear in the palette's **Bundles** section under **Publora**.

## Configure

Set the **Publora API Key** input to your own key from the API page of the
Publora dashboard (app.publora.com/dashboard/api). The components do nothing
until a key is supplied. Social accounts are connected in the Publora
dashboard; the components post only to accounts connected there.

In tool mode, the components expose the tools `publora_list_connections` and
`publora_create_post`.

## Develop

```bash
cd src/bundles/publora
pip install -e .
lfx extension validate src/lfx_publora
```

## Manifest

The extension manifest is shipped at `src/lfx_publora/extension.json` and
points at the bundle at `components/publora`. The components register under
the canonical namespaced IDs
`ext:publora:PubloraListConnectionsComponent@official` and
`ext:publora:PubloraCreatePostComponent@official`.
