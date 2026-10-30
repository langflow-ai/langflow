# lfx-textkit

TextKit SMS and phone verification components as a standalone Langflow Extension Bundle.

[TextKit](https://jointextkit.com) is an SMS API. The bundle calls its REST API
directly with `httpx` and needs only a user-supplied API key, so it carries no
vendor SDK dependency. See the
[TextKit docs](https://jointextkit.com/docs/quickstart) for the API details.

| Component | What it does | Tool name |
| --- | --- | --- |
| `TextKitSendMessageComponent` | Sends an SMS. | `textkit_send_text` |
| `TextKitListMessagesComponent` | Lists sent and received messages, newest first. | `textkit_list_messages` |
| `TextKitSendVerificationComponent` | Texts a one-time code. | `textkit_send_verification` |
| `TextKitCheckVerificationComponent` | Checks a one-time code. | `textkit_check_verification` |

## Install

```bash
pip install lfx-textkit
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components will
appear in the palette's **Bundles** section under **TextKit**.

## Configure

Set the **TextKit API Key** input to a key from the
[TextKit console](https://jointextkit.com/console). A test key
(`ssms_sk_test_...`) simulates sends, and a live key texts real numbers. The
components do nothing until a key is supplied.

## Develop

```bash
cd src/bundles/textkit
pip install -e .
lfx extension validate src/lfx_textkit
```

## Manifest

The extension manifest is shipped at `src/lfx_textkit/extension.json` and points
at the bundle at `components/textkit`. The components register under namespaced
IDs such as `ext:textkit:TextKitSendMessageComponent@official`.
