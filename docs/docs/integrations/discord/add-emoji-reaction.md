import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Add Emoji Reaction

Langflow enhances its functionality with custom components like `DiscordAddEmojiReaction`. This component allows a bot to add emoji reactions to messages within a specified Discord channel.

## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `DiscordAddEmojiReaction` component allows you to:

- Add emoji reactions to messages in a Discord channel.
- Integrate Discord seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `DiscordAddEmojiReaction` component into a Langflow flow:

1. **Add the `DiscordAddEmojiReaction` component** to your flow.
2. **Configure the component** by providing:
   - `Token`: The Discord Application Token (available from the Discord Developers App page).
   - `ChannelId`: The ID of the channel where you want to add emoji reactions.
   - `MessageId`: The ID of the message to which you want to add an emoji reaction (if empty it will react to the last message).
   - `EmojiReaction`: The emoji to add as a reaction (can be Unicode emoji or custom emoji ID).
   - `Message`: A message that goes through the component, used when you want to react to a message but want to follow your flow with a previous message.
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin adding emoji reactions to messages in a Discord channel.

## Code Block for the `DiscordAddEmojiReaction` Component

```python
from typing import Optional, Any
from langflow import CustomComponent
from langflow.field_typing import Data

from langflow import CustomComponent
import subprocess
import sys
import base64
from json import loads
from langflow.schema.dotdict import dotdict

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class DiscordAddEmojiReaction(CustomComponent):
    display_name = "DiscordAddEmojiReaction"
    description = "react to discord message"
    field_order = ["token", "channel_id", "message_id", "reaction", "message"]
    icon = "Discord"

    def build_config(self) -> dict:
        return {
            "token": {
                "display_name": "Token",
                "advanced": False,
                "password": True,
                "required": True,
            }, "channel_id": {
                "display_name": "ChannelId",
                "advanced": False,
                "required": True,
            }, "message_id": {
                "display_name": "MessageId",
                "advanced": False,
                "required": False,
                "value": None,
            }, "reaction": {
                "display_name": "EmojiReaction",
                "advanced": False,
                "required": False,
                "value": None,
            }, "message": {
                "display_name": "Message",
                "advanced": False,
                "required": False,
            }
        }

    def build(self, token: str, channel_id: int, reaction: str, message: str, message_id: Optional[int] = None) -> str:
        import requests

        body = {"token": token}
        if not message_id:
            body = {"token": token, "limit": 1}
            resp = requests.post(f"http://discord:7880/api/v1/channels/{channel_id}/get_messages", json=body)
            if resp.status_code == 200:
                message_id = loads(resp.content)[0]["id"]
            else: raise Exception("Could not retrieve last message")
        body = {"token": token, "emoji": reaction}
        resp = requests.post(f"http://discord:7880/api/v1/channels/{channel_id}/react/{message_id}", json=body)
        return message
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `DiscordAddEmojiReaction` component in a Langflow flow with the specified `Token`, `ChannelId`, `MessageId`, `EmojiReaction`, and `Message`:

<ZoomableImage
  alt="Discord Add Emoji Reaction Flow"
  sources={{
    light: "img/discord/DiscordAddEmojiReaction_flow_example.png",
    dark: "img/discord/DiscordAddEmojiReaction_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `DiscordAddEmojiReaction` component adds a reaction to a Discord channel, then proceeds the flow with its previous message. Ensure you have the correct `Token`, `ChannelId`, `MessageId`, `EmojiReaction`, and `Message` for successful operation.

</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">

When using the `DiscordAddEmojiReaction` component:

- Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
- Verify the `Token` is correct.
- Verify that you have the Discord bundle component running with langflow.
- Ensure the `channelId`, `messageId`, and `emoji` used are correct and accessible by the bot.
- Keep your Discord integration token secure.
- Test the setup in a private channel before production deployment.

</Admonition>

## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `DiscordAddEmojiReaction` component, consider the following:

- Verify the Discord integration token’s validity and permissions.
- Consult the Discord Developers APP Page for documentation updates.

</Admonition>