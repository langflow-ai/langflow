# lfx-unirate

UniRate currency-conversion component as a standalone Langflow Extension Bundle.

The bundle ships a single component, `UniRateConversionComponent`, which converts
an amount from one currency to another using live exchange rates from the
[UniRate API](https://unirateapi.com) and returns the converted amount and rate
as a table. It calls the UniRate convert endpoint directly with `httpx` and needs
only a user-supplied API key, so it carries no vendor SDK dependency.

## Install

```bash
pip install lfx-unirate
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the
`UniRateConversionComponent` will appear in the palette's **Bundles** section
under **UniRate**.

## Configure

Set the **UniRate API Key** input to your own key from
[unirateapi.com](https://unirateapi.com) (a free tier is available). The
component is optional and does nothing until a key is supplied, so it changes
nothing for anyone who does not use it. Set **To Currency** (required),
**From Currency** (defaults to `USD`) and **Amount** (defaults to `1`).

In tool mode, the component exposes a single tool named `convert_currency`.

## Develop

```bash
cd src/bundles/unirate
pip install -e .
lfx extension validate src/lfx_unirate
```

## Manifest

The extension manifest is shipped at `src/lfx_unirate/extension.json` and
points at the bundle at `components/unirate`. The component registers under
the canonical namespaced ID `ext:unirate:UniRateConversionComponent@official`.
