# lfx-twittrapi

TwittrAPI components for public X (Twitter) data as a standalone Langflow
Extension Bundle.

The bundle ships six read-only components that call the
[TwittrAPI](https://www.twittrapi.com) REST API directly with `httpx`. They
need only a user-supplied API key, so the bundle carries no vendor SDK
dependency. See the [TwittrAPI docs](https://www.twittrapi.com/docs) for the
API details.

| Component | Endpoint | Output |
|-----------|----------|--------|
| `TwittrAPISearchTweetsComponent` | `GET /search` | Table of posts (or users for the People category) |
| `TwittrAPIGetUserComponent` | `GET /user/by/username/{username}` | Data (one profile) |
| `TwittrAPIUserTweetsComponent` | `GET /user/{userId}/tweets` | Table of posts |
| `TwittrAPIFollowersComponent` | `GET /user/{userId}/followers` | Table of users |
| `TwittrAPIListTweetsComponent` | `GET /lists/tweets` | Table of posts |
| `TwittrAPITrendsComponent` | `GET /trends/{locationId}` | Table of trends |

Every request asks for `format=simple`, which returns flat camelCase JSON.

## Install

```bash
pip install lfx-twittrapi
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components
will appear in the palette's **Bundles** section under **TwittrAPI**.

## Configure

Set the **TwittrAPI Key** input to your own key from
[twittrapi.com](https://www.twittrapi.com). The input defaults to the
`TWITTRAPI_API_KEY` global variable, so you can also create that variable
or export `TWITTRAPI_API_KEY` in the environment Langflow runs in. The
components do nothing until a key is supplied.

Paginated components (search, user tweets, followers, list tweets) take an
optional **Cursor** input and log the next page's cursor as `next_cursor`.

In tool mode, each component exposes one tool: `twittrapi_search_tweets`,
`twittrapi_get_user`, `twittrapi_user_tweets`, `twittrapi_followers`,
`twittrapi_list_tweets` and `twittrapi_trends`.

## Develop

```bash
cd src/bundles/twittrapi
pip install -e .
lfx extension validate src/lfx_twittrapi
```

## Manifest

The extension manifest is shipped at `src/lfx_twittrapi/extension.json` and
points at the bundle at `components/twittrapi`. The components register under
canonical namespaced IDs such as
`ext:twittrapi:TwittrAPISearchTweetsComponent@official`.
