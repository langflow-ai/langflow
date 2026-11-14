# lfx-specstream

SpecStream web data component as a standalone Langflow Extension Bundle.

The bundle ships a single component, `SpecStreamFindListComponent`, which
reads a request written in plain words through the
[SpecStream](https://specstream.ai) HTTP API and returns structured rows. Each
row has a source URL and the time it was read. It calls the API directly with
`httpx` and needs only a user-supplied API key, so it carries no vendor SDK
dependency. See the [SpecStream API docs](https://specstream.ai/docs/api) for
the API details.

## Install

```bash
pip install lfx-specstream
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the
`SpecStreamFindListComponent` will appear in the palette's **Bundles** section
under **SpecStream**.

## Configure

Set the **SpecStream API Key** input to your own key. Create one under
**Agents & API** in your SpecStream workspace. The component is optional and
does nothing until a key is supplied, so it changes nothing for anyone who
does not use it.

Before anything runs, SpecStream quotes the most the request can cost. The
component stops with an error if that quote is above **Maximum Price (USD)**.
Number of results, a run key and the wait time are the other inputs. The run
key and the wait time are advanced inputs.

In tool mode, the component exposes the request as the tool input. The
maximum price is a component setting that the agent cannot change.

## Develop

```bash
cd src/bundles/specstream
pip install -e .
lfx extension validate src/lfx_specstream
```

## Manifest

The extension manifest is shipped at `src/lfx_specstream/extension.json` and
points at the bundle at `components/specstream`. The component registers under
the canonical namespaced ID `ext:specstream:SpecStreamFindListComponent@official`.
