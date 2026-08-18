# lfx-serply

Serply SERP API web-search component as a standalone Langflow Extension Bundle.

The bundle ships a single component, `SerplySearchComponent`, which runs a
web search through [Serply](https://serply.io) and returns the organic Google
results as a table. It calls the Serply search endpoint directly with `httpx`
and needs only a user-supplied API key, so it carries no vendor SDK dependency.
See the [Serply docs](https://serply.io/docs) for the API details.

## Install

```bash
pip install lfx-serply
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the
`SerplySearchComponent` will appear in the palette under the `serply`
bundle group.

## Configure

Set the **Serply API Key** input to your own key from
[serply.io](https://serply.io). The component is optional and does nothing
until a key is supplied, so it changes nothing for anyone who does not use it.

## Develop

```bash
cd src/bundles/serply
pip install -e .
lfx extension validate .
```

## Manifest

The extension manifest is shipped at `src/lfx_serply/extension.json` and
points at the bundle at `components/serply`. The component registers under
the canonical namespaced ID `ext:serply:SerplySearchComponent@official`.
