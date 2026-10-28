# lfx-serpkite

SerpKite Google search and AI assistant components as a standalone Langflow Extension Bundle.

The bundle ships two components. `SerpKiteSearchComponent` runs a web
search through [SerpKite](https://serpkite.com) and returns the organic
Google results as a table. `SerpKiteAssistantComponent` asks ChatGPT, Gemini,
Copilot Search, Google AI Mode or Brave AI as a logged-out visitor and returns
the answer with its cited sources as a message. Both call the SerpKite
endpoints directly with `httpx` and needs only a user-supplied API key, so it
carries no vendor SDK dependency. See the
[SerpKite docs](https://serpkite.com/docs) for the API details.

## Install

```bash
pip install lfx-serpkite
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; both components
appear in the palette's **Bundles** section under **SerpKite**.

## Configure

Set the **SerpKite Key** input to your own key from
[the dashboard](https://app.serpkite.com/keys). The component is optional and does
nothing until a key is supplied, so it changes nothing for anyone who does
not use it. Country (`country`), language (`language`), location, max results (10-100)
and page (1-10) are optional advanced inputs.

In tool mode, the search component exposes a tool named `serpkite_search`
and the assistant component one named `serpkite_ask_assistant`. Assistant
answers take from a few seconds (Brave AI) to under a minute; the component
waits up to 120 seconds.

## Develop

```bash
cd src/bundles/serpkite
pip install -e .
lfx extension validate src/lfx_serpkite
```

## Manifest

The extension manifest is shipped at `src/lfx_serpkite/extension.json` and
points at the bundle at `components/serpkite`. The components register under
the canonical namespaced IDs `ext:serpkite:SerpKiteSearchComponent@official`
and `ext:serpkite:SerpKiteAssistantComponent@official`.

Maintained by the SerpKite team. Google is a trademark of Google LLC.
