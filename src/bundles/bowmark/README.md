# lfx-bowmark

Bowmark components as a standalone Langflow Extension Bundle.

[Bowmark](https://bowmark.ai) runs tasks on live websites and returns typed
results. The bundle ships two components:

- `BowmarkLibraryComponent` (**Bowmark Library**): look up which functions
  Bowmark has for a website or task, for example `linkedin.com` or
  `flight prices`. Returns their names, arguments and return types as text.
- `BowmarkRunComponent` (**Bowmark Run**): run a short JavaScript script that
  calls those functions and return the result as `Data`, with the run id and
  logs.

Both call the Bowmark HTTP API directly with `httpx` and need only a
user-supplied API key, so the bundle carries no vendor SDK dependency.

## Install

```bash
pip install lfx-bowmark
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; both components
appear in the palette's **Bundles** section under **Bowmark**.

## Configure

Set the **Bowmark API Key** input to your own key from
[bowmark.ai](https://bowmark.ai). The components do nothing until a key is
supplied, so they change nothing for anyone who does not use them.

In tool mode, give an Agent both: it calls `bowmark_get_library` to find the
functions for a site, then `bowmark_run` with a script such as:

```js
return (await bowmark.providers.hackernews.topStories()).slice(0, 3)
```

## Develop

```bash
cd src/bundles/bowmark
pip install -e .
lfx extension validate src/lfx_bowmark
```

## Manifest

The extension manifest is shipped at `src/lfx_bowmark/extension.json` and
points at the bundle at `components/bowmark`. The components register under
`ext:bowmark:BowmarkLibraryComponent@official` and
`ext:bowmark:BowmarkRunComponent@official`.
