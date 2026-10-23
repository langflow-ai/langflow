# Telegram bot integration

The Telegram bundle supplies new text-message and bot-command triggers, plain-text messages, replies, and notifications. Every component uses a Telegram connection. A trigger accepts an explicit allowlist of numeric chat IDs and optional sender IDs. Group messages remain subject to the bot's Telegram privacy settings.

This release supports one active trigger per validated bot account in a Langflow database. Choose either On Message or On Command for each bot. The durable claim covers duplicate connections, both trigger kinds, polling, and webhooks. Additional flows need additional bots. Multi-flow fanout is outside this release.

## Installation and connection

The curated Langflow distribution includes lfx-telegram. Install it alongside a bundle-free Langflow build to add the same components and server adapter. The bundle registers its components through langflow.extensions and its server adapter through langflow.trigger_providers. Standalone actions require lfx. Server triggers also require langflow-base.

Create a bot through BotFather. Add its token as your own Telegram connection with the bot identity. Langflow verifies getMe before saving the connection and replaces caller-supplied account metadata with Telegram's bot ID and username. Telegram bot tokens have no OAuth scopes, refresh tokens, or automatic refresh. The capability manifest declares no invented scope grants.

Before enabling a trigger, allow background runs on its connection. Set at least one allowed chat ID. Numeric IDs are required because an incoming update identifies a chat numerically. Usernames and request URLs are not target inputs. An optional sender allowlist excludes messages with unrecognized or anonymous senders.

Add the bot to the required group or start its private conversation first. Review the bot's BotFather privacy settings and group permissions. A chat allowlist filters updates Telegram actually sends. It cannot grant visibility to other messages. Messages from bots and anonymous senders, channel posts, edits, attachments, callbacks, and business-account events do not start these triggers. The command trigger requires a leading bot_command entity. A command addressed to another bot is ignored. Re-enable a webhook trigger after changing its bot username so named commands use the new name.

## Supported transports

| Context | Trigger receiver | Actions |
| --- | --- | --- |
| Hosted | Public HTTPS webhook | Supported |
| Self-managed with public HTTPS ingress | Webhook or polling | Supported |
| Self-managed without public ingress | Polling | Supported |
| Desktop | Polling | Supported |
| Headless executor | No standalone receiver | Supported through a connection resolver |

For push delivery, configure LANGFLOW_TRIGGER_INGRESS_ENABLED and an operator-owned LANGFLOW_TRIGGER_INGRESS_ORIGIN. Use public HTTPS on a Telegram-supported port. The server generates an opaque receiver URL and a separate secret header value. The flow never contains the bot token or webhook secret. Each delivery must provide the matching X-Telegram-Bot-Api-Secret-Token header before its body can enter the ledger.

The default delivery mode follows the deployment's available transport. Polling checks receiver ownership on its first collection and refuses any existing webhook before calling getUpdates. Webhook setup refuses an unrelated existing URL. Langflow never clears an existing webhook merely to make polling work.

## Messages, replies, and sessions

Send Message and Send Notification call sendMessage as the connected bot. The notification component defaults to a silent notification. Both accept a numeric chat ID and an optional topic ID. They send plain text, with a conservative limit of 4096 UTF-16 units. Formatting modes, arbitrary API methods, file downloads, and paid broadcasts are unavailable.

Reply to Message accepts a Telegram trigger event and preserves its chat, topic, and message ID. It verifies that the selected connection belongs to the receiving bot before sending. A missing reply target fails rather than becoming an unrelated top-level message.

Thread sessions use the bot, chat, and Telegram topic ID only when Telegram marks the message as a topic message. This includes forum supergroups and private chats with bot forum mode enabled. Ordinary replies keep the default chat session and use the original message ID without a forum destination. Sender sessions use the bot, chat, and sender ID. Chat sessions use the bot and chat. The normalized payload includes these IDs, the update and message IDs, text, command arguments, and the stable session key. Bot credentials embedded in message text are redacted. Unknown raw update fields are omitted.

## Delivery and recovery

Polling reads one page of at most 100 updates per source round. The next offset and normalized events commit together. A later request confirms only the prior committed page. A failed commit repeats the original offset and replays the page safely. Empty polls clear the pending offset, and an offset older than seven days is omitted because Telegram can randomize the next update ID after inactivity.

Webhook and polling intake use the same canonical bot ID and update ID. The durable ledger and source-version records suppress redelivery across a transport change. The shared runtime leases polling work and fences durable commits when replica ownership changes. The bot claim persists independently of a process or lease timeout.

Telegram retains pending updates for at most 24 hours. Downtime beyond that window can lose provider events. Langflow cannot reconstruct them from message history. A send that times out may already have reached Telegram. The action does not retry ambiguous failures automatically. An authentication rejection permits one credential re-resolution. Rate-limit failures expose Telegram's retry_after value without response text or credential URLs. Operators should keep ordinary sends below Telegram's per-chat and bot-wide limits.

Disable the trigger and wait for receiver cleanup before changing transport or replacing its connection. Both setWebhook and deleteWebhook explicitly retain pending updates. Pause or deletion queues durable cleanup. Cleanup checks the original bot ID and current webhook URL before deletion. It leaves a different URL untouched. Pending cleanup blocks a replacement receiver, even after the old trigger is deleted.

Complete cleanup before revoking or rotating a token. A deleted connection or invalid token can leave a nonexpiring webhook and an unresolved cleanup intent. Restore access to the original bot or reconcile that intent administratively before enabling a replacement. Langflow does not clear the claim merely because a timeout has elapsed.

## Bot-wide ownership limits

Dedicate each bot to one Langflow installation. Telegram exposes one webhook and one getUpdates queue per bot. Its API has no compare-and-delete operation for webhook ownership and cannot prove that an unrelated polling client is idle. Langflow prevents conflicting receivers within its own database. It cannot coordinate another installation or application that holds the same token. A remote application can still replace a webhook between an ownership check and a deletion request. Do not share a bot token across receivers.

## Evidence and limits

Contract tests use synthetic Bot API responses, real component execution, real credential leases, and real SQLite uniqueness constraints. They do not establish acceptance against a live Telegram bot or prove a production replica failover. Those external checks remain unverified.

The implementation follows the official [Bot API](https://core.telegram.org/bots/api), [update transport contract](https://core.telegram.org/bots/api#getting-updates), [webhook setup](https://core.telegram.org/bots/api#setwebhook), [message API](https://core.telegram.org/bots/api#sendmessage), and [privacy and rate-limit guidance](https://core.telegram.org/bots/faq). These sources were checked on October 22, 2026.
