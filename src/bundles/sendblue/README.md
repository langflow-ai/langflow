# Sendblue for Langflow

This bundle provides a Sendblue component for one-to-one messages, bounded message history, delivery status and sending line state. Install `lfx-sendblue` alongside a compatible Langflow installation (LFX 1.13 or later).

Create an API key and secret in your [Sendblue dashboard](https://app.sendblue.com/) and enter both in the component's secret inputs. Select an operation; reads are the default. The component contacts only `https://api.sendblue.co` and does not log credentials, phone numbers or message text.

For sends, enable **Allow Sending** after reviewing your flow, specify an E.164 recipient and exact message, and use a human approval step for agent-selected sends. Free shared-line plans require an explicit sending line and a verified recipient. Sending is asynchronous: retain the message handle and use **Get Message Status**. A network timeout may happen after acceptance; check history before retrying. The component never automatically retries sends.

**List Messages** returns a single page (limit 1–100) and preserves response pagination metadata. Use the phone filter to narrow a conversation, and offset to fetch later pages.

Run tests using the repository bundle test environment: `uv run pytest src/bundles/sendblue/tests`.

[Sendblue API documentation](https://docs.sendblue.com/) · [Privacy](https://www.sendblue.com/privacy-policy) · support@sendblue.com
