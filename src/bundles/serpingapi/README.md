# lfx-serpingapi

Serping API Google SERP web-search component as a standalone Langflow Extension Bundle.

The bundle ships a single component, `SerpingApiSearchComponent`, which runs
a web search through the [Serping API](https://serpingapi.com) and returns
the organic Google results as a table. It calls the Serping API search
endpoint directly with `httpx` and needs only a user-supplied API key, so it
carries no vendor SDK dependency. See the
[Serping API docs](https://serpingapi.com/docs) for the API details.

## Install

```bash
pip install lfx-serpingapi
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the
`SerpingApiSearchComponent` will appear in the palette's **Bundles** section
under **Serping API**.

## Configure

Set the **Serping API Key** input to your own key from
[serpingapi.com](https://serpingapi.com). The component is optional and does
nothing until a key is supplied, so it changes nothing for anyone who does
not use it. Country (`gl`), language (`hl`), location, max results (1-100)
and page are optional advanced inputs.

In tool mode, the component exposes a single tool named `serpingapi_search`.

## Develop

```bash
cd src/bundles/serpingapi
pip install -e .
lfx extension validate src/lfx_serpingapi
```

## Manifest

The extension manifest is shipped at `src/lfx_serpingapi/extension.json` and
points at the bundle at `components/serpingapi`. The component registers under
the canonical namespaced ID `ext:serpingapi:SerpingApiSearchComponent@official`.
