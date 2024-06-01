import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Text Message Listener

Langflow enhances its functionality with custom components like `DiscordTextMessageListener`. This component listens for messages within a specified Discord channel for up to 5 minutes or until a message is received.

## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `DiscordTextMessageListener` component allows you to:

- Monitor new messages in a Discord channel.
- Activate upon detecting a new message in a Discord channel.
- Integrate Discord seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `DiscordTextMessageListener` component into a Langflow flow:

1. **Add the `DiscordTextMessageListener` component** to your flow.
2. **Configure the component** by providing:
   - `Token`: The Discord Application Token (available from the Discord Developers App page).
   - `ChannelId`: The ID of the channel from which you want to listen for messages (can be found by right-clicking the channel with Discord Developer Mode enabled).
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin monitoring for new messages in a Discord channel and to retrieve message text.

## Code Block for the `DiscordTextMessageListener` Component

```python
from langflow import CustomComponent
import subprocess
import sys
import requests

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install("requests")

class DiscordTextMessageListener(CustomComponent):
    display_name = "DiscordTextMessageListener"
    description = "Listens for messages from a specified Discord channel."
    field_order = ["token", "channel_id"]
    icon = "Discord"

    def build_config(self) -> dict:
        return {
            "token": {
                "display_name": "Token",
                "advanced": False,
                "password": True,
                "required": True,
            },
            "channel_id": {
                "display_name": "ChannelId",
                "advanced": False,
                "required": True,
            }
        }

    def build(self, token: str, channel_id: int) -> str:
        response = requests.post("http://discord:7880/api/v1/listen_message", json={"token": token, "channel_id": channel_id})
        if response.status_code == 200:
            return response.content
        else:
            raise Exception("Failed to retrieve message or timeout occurred.")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `DiscordTextMessageListener` component in a Langflow flow with the specified `ChannelId` and `Token`:

<ZoomableImage
  alt="Discord Listen Message Flow"
  sources={{
    light: "img/discord/DiscordTextMessageListener_flow_example.png",
    dark: "img/discord/DiscordTextMessageListener_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `DiscordTextMessageListener` component connects to a text output node to display received messages. Ensure you have the correct `ChannelId` and `Token` for successful operation.

</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">

When using the `DiscordTextMessageListener` component:

- Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
- Verify the `Token` is correct.
- Ensure the `ChannelId` used is correct and accessible by the bot.
- Keep your Discord integration token secure.
- Test the setup in a private channel before production deployment.

</Admonition>

## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `DiscordTextMessageListener` component, consider the following:

- Verify the Discord integration token’s validity and permissions.
- Consult the Discord Developers APP Page for documentation updates.
- Ensure the `ChannelId` is correct.

</Admonition>