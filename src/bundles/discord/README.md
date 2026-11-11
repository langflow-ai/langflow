# Discord integration

This bundle provides connection-backed Discord bot actions and Gateway event triggers.

Tool Mode is available for Send Message and Reply to Message. Configure the bot connection on the component. Send Message lets the agent supply the guild, channel or thread, and text. Reply to Message keeps its trigger event configured so the bot and reply target come from that event, while the agent supplies the text. Event triggers do not expose Tool Mode.

See the [Discord integration setup guide](https://docs.langflow.org/next/bundles-discord) for installation, permissions, supported environments, receiver setup, and recovery. The guide's source is [bundles-discord.mdx](../../../docs/docs/Components/bundles-discord.mdx).
