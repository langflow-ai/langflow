# Discord bot messages and Gateway triggers

This preview adds On Message and On Mention triggers, Send Message, and Reply to Message. The trigger provides a Message output with a stable conversation session. A channel or thread gets its own session. The optional sender setting separates users within that channel.

## Setup

Create a Discord application and bot in the Developer Portal. Install the bot into the target guild with the bot installation scope. Grant View Channel and Send Messages. Replies also require Read Message History. Threads need Send Messages in Threads and membership when the thread is private. These are Discord permissions, not OAuth token scopes.

Create a user-owned Discord connection with that application's bot token. The connection service verifies both the bot user and current application before saving the identity. Tokens do not expire on a fixed schedule and have no refresh token. Reset a revoked token in Discord and reconnect the connection. Never paste tokens into component inputs.

Enable background-run consent on that connection. Add one receiver with a guild ID and between 1 and 100 explicit text channel or thread IDs. Enable developer mode in Discord to copy IDs. The listener checks each channel's guild before connecting. Thread IDs are explicit targets. Selecting a parent does not select its threads.

On Message requires Message Content Intent enabled in the Developer Portal. Discord approval is also required when applicable to the bot. On Mention requests only standard Guilds and Guild Messages intents. Discord provides content for messages mentioning the app without the privileged content intent. Both triggers ignore bot authors, webhook posts, edits, deletions, DMs, and unsupported message types.

Run the API and the separate langflow listeners process with the same database, secret key, and installed bundle. The listener dials the fixed Discord API and validated Discord Gateway hosts. No public ingress is needed. Gateway triggers are supported on self-managed deployments only. Actions support hosted, self-managed, Desktop, and headless contexts where the connection resolver is available.

## Receiver ownership and recovery

One active trigger may reserve a verified bot on this Langflow database. Duplicate bot connections cannot create additional receivers. Disable a receiver and finish its durable cleanup before enabling a replacement. Cleanup never deletes or mutates the Discord application. The supervisor closes the old leased socket. Event and cursor writes check the captured lease generation. Event writes also check the active trigger, owner, connection, and exact configuration before committing.

The client sends protocol heartbeats and reconnects through the supervisor's bounded backoff. Local socket teardown preserves Discord resume eligibility for a handover. Pausing and enabling a fresh receiver clears its saved session. Resume uses the saved session and last durably handled sequence. Message IDs deduplicate replayed creates. The resume cursor advances after the event commit, so a crash between those writes can replay a message but cannot advance past an uncommitted event. Discord can invalidate sessions and discard its replay window. A new Identify starts with current events. This preview does not backfill missed history after invalidation, long downtime, pause, or bot removal.

Protocol frame logging is disabled even when application logging uses DEBUG. Operational errors still use the supervisor's sanitized error reporting.

The receiver checks Discord's session start allowance before Identify and spaces its own repeated Identify attempts. Only single-shard bots are supported. Other processes using the same bot token still consume its Discord-wide allowance. Do not run another Gateway client with this token. Authentication and disallowed-intent close codes require reconnecting the connection after fixing the bot settings. Rate limits return a typed error with the provider's retry delay.

## Replies and limits

Send Message accepts plain text of at most 2000 UTF-16 code units. Reply to Message preserves the event's verified bot, guild, and channel or thread. It requests an actual Discord message reply and fails when the original message is unavailable. Mentions are disabled for both actions. Messages include a nonce derived from the run and component when available. Discord only deduplicates that nonce for its documented recent window. Ambiguous write failures are not retried automatically.

Slash commands, interaction responses, ephemeral messages, and HTTP interaction endpoints are unsupported. Discord requires an initial interaction response within three seconds and uses temporary response tokens. Those tokens have no supported storage path in this runtime and never enter the ledger. This implementation does not acknowledge commands or substitute a channel post for an interaction response.

## Verification boundary

Synthetic HTTP and WebSocket contracts cover requests, identity, intents, filtering, resume, heartbeat failure, and safe error handling. Database tests exercise ownership, consent, policy, receiver uniqueness, pause, and queued cleanup. These checks do not establish live tenant acceptance. A real Discord guild, token rotation, rolling deployment, reconnect replay window, and effective channel permissions remain unverified. Owner acceptance remains pending.

## Official sources

The current protocol and API contracts were checked on October 22, 2026.

- [Gateway connections and intents](https://docs.discord.com/developers/events/gateway)
- [Gateway events](https://docs.discord.com/developers/events/gateway-events)
- [Gateway close codes](https://docs.discord.com/developers/topics/opcodes-and-status-codes)
- [Applications and bot identity](https://docs.discord.com/developers/resources/application)
- [Message creation and nonce behavior](https://docs.discord.com/developers/resources/message)
- [Channel permissions](https://docs.discord.com/developers/topics/permissions)
- [Rate limits](https://docs.discord.com/developers/topics/rate-limits)
- [Interaction response deadlines](https://docs.discord.com/developers/interactions/receiving-and-responding)
