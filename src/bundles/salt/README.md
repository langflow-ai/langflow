# lfx-salt

Salt agent components as a standalone Langflow Extension Bundle.

[Salt](https://saltapp.ai) is a chat app where people and software agents share
end-to-end encrypted chats. The bundle lets a flow act as a Salt agent with its
own API key. It ships six components:

| Component | What it does |
| --- | --- |
| `SaltSendMessageComponent` | Send an encrypted message into a chat. |
| `SaltAskHumanComponent` | Post a question card with up to five buttons, then check for the tap. |
| `SaltRequestPaymentComponent` | Post a payment request into a chat. |
| `SaltReadUpdatesComponent` | Check for new Salt events (messages, card taps) on demand. |
| `SaltReadRoomComponent` | Read a chat's session and recent messages. |
| `SaltInterestsComponent` | Set, read or clear the agent's follow settings for a chat. |

The components use the [`saltapp`](https://pypi.org/project/saltapp/) Python SDK
for the API client, message encryption and webhook-signature verification.

## Install

```bash
pip install lfx-salt
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components appear
in the palette's **Bundles** section under **Salt**.

## Configure

Each component takes the agent's Salt host, agent ID and API key. The bundle is
optional and does nothing until an agent is configured, so it changes nothing
for anyone who does not use it. Create an agent and its API key in the Salt app
or with the `saltapp` SDK.

`Salt Ask Human` and `Salt Read Updates` check for answers and events each time they run,
rather than waiting for a webhook. `Salt Read Updates` keeps a small cursor file under
`~/.salt/agents` (override with `SALTAPP_LANGFLOW_STATE_DIR`) so a repeated run
does not return the same event twice.

## Develop

```bash
cd src/bundles/salt
pip install -e .
lfx extension validate src/lfx_salt
```

## Manifest

The extension manifest is shipped at `src/lfx_salt/extension.json` and points at
the bundle at `components/salt`. Components register under IDs such as
`ext:salt:SaltSendMessageComponent@official`.
