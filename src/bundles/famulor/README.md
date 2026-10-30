# lfx-famulor

Famulor voice-agent components as a standalone Langflow Extension Bundle.

The bundle ships four components that call the public [Famulor REST API](https://docs.famulor.io/api-reference/introduction) at `https://app.famulor.io/api/v1`:

- `FamulorMakeCallComponent` starts an outbound AI call.
- `FamulorGetCallComponent` reads a call's status, summary, and transcript.
- `FamulorListAssistantsComponent` lists workspace assistants.
- `FamulorListCampaignsComponent` lists campaigns.

Each component sends `Authorization: Bearer <api key>` with `httpx` and needs only a user-supplied API key, so the bundle carries no vendor SDK dependency.

## Install

```bash
pip install lfx-famulor
```

The bundle is registered automatically via the `langflow.extensions` entry-point. After install, restart your Langflow server. The components appear in the palette's **Bundles** section under **Famulor**.

The bundle is not part of the default `pip install langflow` install. It is included in `pip install "langflow[bundles]"`.

## Configure

Set **Famulor API Key** to a workspace key (`fam_...`) from **Settings, API & MCP** at [app.famulor.io](https://app.famulor.io). The components do nothing until a key is supplied.

In tool mode, each component exposes one tool: `famulor_make_call`, `famulor_get_call`, `famulor_list_assistants`, or `famulor_list_campaigns`. The API key stays on the component and is not a tool argument.

## Develop

```bash
cd src/bundles/famulor
pip install -e .
lfx extension validate src/lfx_famulor
```

## Manifest

The extension manifest is shipped at `src/lfx_famulor/extension.json` and points at the bundle at `components/famulor`. Components register under canonical namespaced IDs such as `ext:famulor:FamulorMakeCallComponent@official`.
