# lfx-uploadpost

Upload-Post social publishing components as a standalone Langflow Extension Bundle.

[Upload-Post](https://upload-post.com) publishes one video, set of photos or
text post to TikTok, Instagram, YouTube, LinkedIn, Facebook, X, Threads,
Pinterest and Bluesky in a single call. The bundle calls the Upload-Post REST
API directly with `httpx` and needs only a user-supplied API key, so it
carries no vendor SDK dependency. See the
[Upload-Post API docs](https://docs.upload-post.com) for details.

| Component | What it does |
|---|---|
| `UploadPostVideoComponent` | Publish a video (file or public URL) |
| `UploadPostPhotosComponent` | Publish one or more photos; several make a carousel |
| `UploadPostTextComponent` | Publish a text post |
| `UploadPostStatusComponent` | Look up the per-platform result by `request_id` or scheduled `job_id` |

## Install

```bash
pip install lfx-uploadpost
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components
appear in the palette's **Bundles** section under **Upload-Post**.

## Configure

1. Create an Upload-Post account, create a profile and connect the social
   accounts you want to post from.
2. Create an API key and set it on the **Upload-Post API Key** input.
3. Set **Profile** to that profile's name.

The components do nothing until a key is supplied, so they change nothing for
anyone who does not use them.

## How publishing behaves

- **One request, many platforms.** Each platform comes back with its own
  result: `completed` (with URL or post id), `failed` (with the platform's
  error) or `skipped` (no account for it on the profile).
- **One upload per run.** The component generates a `request_id`, sends it as
  the `Idempotency-Key`, and never re-sends after a network error: it checks
  that `request_id` to learn whether the upload arrived. This protects a single
  run only. Running the component again is a new request and a new post, so if
  a run reports an unconfirmed upload, look up its `request_id` with
  **Upload-Post Status** first.
- **Safe defaults.** YouTube uploads default to `private`; TikTok keeps the
  account's own privacy unless you pick one.
- **Scheduling.** Set **Schedule At** (ISO-8601, with an optional IANA
  **Timezone**) to publish later; the output carries the `job_id`.

## Develop

```bash
cd src/bundles/uploadpost
pip install -e .
lfx extension validate src/lfx_uploadpost
```

## Manifest

The extension manifest is shipped at `src/lfx_uploadpost/extension.json` and
points at the bundle at `components/uploadpost`. The components register
under canonical namespaced IDs such as
`ext:uploadpost:UploadPostVideoComponent@official`.
