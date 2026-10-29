# lfx-mailtrap

Mailtrap email components (send, Email Sandbox) as a standalone Langflow Extension Bundle.

The bundle lets a flow or an Agent send and test email through
[Mailtrap](https://mailtrap.io). It calls Mailtrap through the official
[`mailtrap` Python SDK](https://github.com/mailtrap/mailtrap-python) and needs
only a user-supplied API token.

| Component | What it does |
|-----------|--------------|
| `MailtrapSendEmailComponent` | Send one email on the Transactional or Bulk stream, or into an Email Sandbox inbox. |
| `MailtrapListSandboxMessagesComponent` | List the messages in an Email Sandbox inbox. |
| `MailtrapGetSandboxMessageComponent` | Get one Sandbox message with its text and HTML bodies. |
| `MailtrapCheckSandboxMessageComponent` | Get the spam score and the HTML analysis of a Sandbox message. |

## Install

```bash
pip install lfx-mailtrap
```

The bundle registers itself through the `langflow.extensions` entry point.
After you install it, restart your Langflow server. The components then appear
in the palette's **Bundles** section under **Mailtrap**.

## Configure

Set the **Mailtrap API Token** input to a token from
[mailtrap.io/api-tokens](https://mailtrap.io/api-tokens). The token needs
access to the sending domain or the Email Sandbox inbox that the component
uses. The Sandbox read components also need your **Account ID**.

**Mailtrap: Send Email** has an optional **Allowed Recipient Domains** input.
If you set it, the component rejects any recipient outside the listed domains
and addresses before it sends a request. This stops an Agent from sending
email to any address it picks.

The components only call the fixed Mailtrap API hosts. No component has a
URL or host input.

In tool mode, each component exposes one tool, for example
`mailtrap_send_email` or `mailtrap_check_sandbox_message`.

## Develop

```bash
cd src/bundles/mailtrap
pip install -e .
lfx extension validate src/lfx_mailtrap
```

## Manifest

The extension manifest is at `src/lfx_mailtrap/extension.json` and points at
the bundle at `components/mailtrap`. Each component registers under a namespaced
ID, for example `ext:mailtrap:MailtrapSendEmailComponent@official`.
