# lfx-google

Google and Gemini components as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-google
```

`pip install langflow` includes this bundle because Google Generative AI is a
supported model provider. The bundle is registered automatically through the
`langflow.extensions` entry point and appears under the `google` group with
canonical component IDs such as
`ext:google:GoogleGenerativeAIComponent@official`.

## Develop

```bash
uv sync
uv run pytest src/bundles/google/tests -q
uv run lfx extension validate src/bundles/google/src/lfx_google
```

The bundle graduated from the manifest-less `lfx-bundles[google]` provider in
Langflow 1.12. Its bundle and class names are unchanged, so existing saved
flows retain their canonical IDs.

## Google Workspace actions

The bundle ships five connection-backed Workspace actions — `GmailSendComponent`,
`GoogleDriveListComponent`, `GoogleDriveFetchComponent`, `GoogleCalendarListComponent`,
and `GoogleCalendarCreateComponent`. They resolve credentials through a managed
connection (`ConnectionRefInput`) rather than a pasted token, and each requests exactly
one scope.

`src/lfx_google/components/google/capabilities.v1.json` is the bundle's capability
manifest, referenced from `extension.json` under `integrations`. It is contract data the
extension loader reads from the *installed* package, so the hatch wheel `include` list
carries `src/lfx_google/components/**/*.json`; a test asserts it is present in a built
wheel.

Scopes are declared as full `https://www.googleapis.com/auth/...` URLs because that is
the form the OAuth broker stores and the resolver compares against.

Live suite (opt-in, needs a real Google account):

```bash
export LF_CONNECTION__GOOGLE__LIVE='{"access_token":"ya29...."}'
export LANGFLOW_GOOGLE_LIVE_CALENDAR_ID=primary
uv run pytest src/bundles/google/tests/test_workspace_actions_live.py -m api_key_required
```

CI deselects `-m api_key_required`, so the live suite never runs without credentials.
