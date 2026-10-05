# lfx-serpkite

SerpKite Google SERP web-search component as a standalone Langflow Extension Bundle.

The bundle ships a single component, `SerpKiteSearchComponent`, which runs
a web search through [SerpKite](https://serpkite.com) and returns
the organic Google results as a table. It calls the SerpKite search
endpoint directly with `httpx` and needs only a user-supplied API key, so it
carries no vendor SDK dependency. See the
[SerpKite docs](https://serpkite.com/docs) for the API details.

## Install

```bash
pip install lfx-serpkite
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the
`SerpKiteSearchComponent` will appear in the palette's **Bundles** section
under **SerpKite**.

## Configure

Set the **SerpKite Key** input to your own key from
[the dashboard](https://app.serpkite.com/keys). The component is optional and does
nothing until a key is supplied, so it changes nothing for anyone who does
not use it. Country (`country`), language (`language`), location, max results (10-100)
and page (1-10) are optional advanced inputs.

In tool mode, the component exposes a single tool named `serpkite_search`.

## Develop

```bash
cd src/bundles/serpkite
pip install -e .
lfx extension validate src/lfx_serpkite
```

## Manifest

The extension manifest is shipped at `src/lfx_serpkite/extension.json` and
points at the bundle at `components/serpkite`. The component registers under
the canonical namespaced ID `ext:serpkite:SerpKiteSearchComponent@official`.

Maintained by the SerpKite team. Google is a trademark of Google LLC.
