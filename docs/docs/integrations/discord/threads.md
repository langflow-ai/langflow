import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Threads

Langflow enhances its functionality with custom components like `DiscordThreads`. This component interacts with threads within a specified Discord channel.

## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `DiscordThreads` component allows you to:

- Get the message threads in a Discord channel.
- Integrate Discord seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `DiscordThreads` component into a Langflow flow:

1. **Add the `DiscordThreads` component** to your flow.
2. **Configure the component** by providing:
   - `Token`: The Discord Application Token (available from the Discord Developers App page).
   - `ChannelId`: The ID of the channel where you want to manage threads.
   - `BotName`: The name of the bot you want to interact with.
   - `Limit`: The limit of messages you want to retrieve (0 means limitless).
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin interacting with threads in a Discord channel.

## Code Block for the `DiscordThreads` Component

```python
from typing import Optional, Any
from langflow import CustomComponent
from langflow.field_typing import Data
import subprocess
import sys
import base64
from json import loads
from langflow.schema.dotdict import dotdict

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class DiscordThreads(CustomComponent):
    display_name = "DiscordThreads"
    description = "get the messages of discord's threads"
    field_order = ["bot_name", "token", "channel_id", "limit"]
    icon = "Discord"

    def build_config(self) -> dict:
        return {
            "bot_name": {
                "display_name": "BotName",
                "advanced": False,
                "required": True,
            }, "token": {
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
                "value": 20,
                "advanced": False,
                "info": "The value 0 means limitless",
                "required": True,
            }
        }

    def update_state(
        self, name: str, value: Any
    ):
        print(name, value, flush=True)
        return super().update_state(name, value)

    def build(self, bot_name: str, token: str, channel_id: int,  limit: int) -> str:
        import requests
        
        body = {"token": token}
        if channel_id:
            body["channel_id"] = channel_id

        resp = requests.post("http://discord:7880/api/v1/listen_mention", json=body)
        if resp.status_code == 200:
            user_input = loads(resp.content)
            user_input_id, user_input_msg = user_input["id"], user_input["content"]
            body = {"token": token, "limit": limit}
            resp = requests.post(f"http://discord:7880/api/v1/channels/{channel_id}/get_messages", json=body)

            if resp.status_code == 200:
                messages = loads(resp.content)[1:]
                messages.reverse()
                messages = str([{"sender": message["author"]["name"], "message": message["message"]} for message in messages])

                return f'Chat Messages: {messages}\n\nChat Message Order: Down to Top\n\nUser Input: {user_input_msg}\nYour name: {bot_name}'
            else:
                raise Exception("Timeout exception")
        else:
            raise Exception("Timeout exception")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `DiscordThreads` component in a Langflow flow with the specified `ChannelId`, `Token`, and `BotName`:

<ZoomableImage
  alt="Discord Threads Flow"
  sources={{
    light: "img/discord/DiscordThreads_flow_example.png",
    dark: "img/discord/DiscordThreads_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `DiscordThreads` component connects to a text output node to manage threads. Ensure you have the correct `ChannelId` and `Token` for successful operation.

</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">

When using the `DiscordThreads` component:

- Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
- Verify the `Token` is correct.
- Ensure the `ChannelId` used is correct and accessible by the bot.
- Keep your Discord integration token secure.
- Test the setup in a private channel before production deployment.

</Admonition>

## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `DiscordThreads` component, consider the following:

- Verify the Discord integration token’s validity and permissions.
- Consult the Discord Developers APP Page for documentation updates.
- Ensure the `ChannelId` is correct.

</Admonition>