import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Mention Response

Langflow enhances its functionality with custom components like `DiscordMentionResponse`. This component responds to messages where the bot is mentioned.

## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `DiscordMentionResponse` component allows you to:

- Respond to mentions in a Discord channel.
- Activate upon detecting a mention in a Discord channel.
- Integrate Discord seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `DiscordMentionResponse` component into a Langflow flow:

1. **Add the `DiscordMentionResponse` component** to your flow.
2. **Configure the component** by providing:
   - `Token`: The Discord Application Token (available from the Discord Developers App page).
   - `ChannelId`: The ID of the channel from which you want to listen for mentions (can be found by right-clicking the channel with Discord Developer Mode enabled).
   - `Message`: A message to answer the Discord mention.
   - `Limit`: The number of context messages to get after triggered by the mention.
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin monitoring for mentions in a Discord channel and to respond accordingly.

## Code Block for the `DiscordMentionResponse` Component

```python
from langflow import CustomComponent
from langflow.field_typing import Data

from langflow import CustomComponent
import subprocess
import sys
import base64
from tempfile import NamedTemporaryFile

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class DiscordMentionResponse(CustomComponent):
    display_name = "DiscordMentionResponse"
    description = "Response channel message mention"
    field_order = ["token", "channel_id", "message", "limit"]
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
            }, "limit": {
                "display_name": "Limit",
                "advanced": False,
                "required": True,
            }, "message": {
                "display_name": "Message",
                "advanced": False,
                "required": True,
            }
        }

    def build(self, token: str, channel_id: int, message: str, limit: int) -> str:
        import requests
        resp = requests.post(
            f"http://discord:7880/api/v1/channels/{channel_id}/mentions/last",
            json={
                "token": token,
                "limit": limit,
            }
        )
        if resp.status_code == 200:
            msg_reference = loads(resp.content)["id"]
            resp = requests.post(
                f"http://discord:7880/api/v1/channels/{channel_id}/send_message",
                json={
                    "token": token,
                    "message": message,
                    "reference": msg_reference,
                }
            )
            if resp.status_code == 200:
                return "Sent successfully message:" + message
        print("err", str(resp.content))
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `DiscordMentionResponse` component in a Langflow flow with the specified `ChannelId` and `Token`:

<ZoomableImage
  alt="Discord Mention Response Flow"
  sources={{
    light: "img/discord/DiscordMentionResponse_flow_example.png",
    dark: "img/discord/DiscordMentionResponse_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `DiscordMentionResponse` component connects to a text output node to display responses to mentions. Ensure you have the correct `ChannelId` and `Token` for successful operation.

</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">

When using the `DiscordMentionResponse` component:

- Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
- Verify the `Token` is correct.
- Ensure the `ChannelId` used is correct and accessible by the bot.
- Keep your Discord integration token secure.
- Test the setup in a private channel before production deployment.

</Admonition>

## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `DiscordMentionResponse` component, consider the following:

- Verify the Discord integration token’s validity and permissions.
- Consult the Discord Developers APP Page for documentation updates.
- Ensure the `ChannelId` is correct.

</Admonition>