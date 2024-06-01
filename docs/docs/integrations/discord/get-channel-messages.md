import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Get Channel Messages

Langflow enhances its functionality with custom components like `DiscordGetChannelMessages`. This component retrieves message history from a specified Discord channel.

## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `DiscordGetChannelMessages` component allows you to:

- Retrieve message history from a Discord channel.
- Integrate Discord seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `DiscordGetChannelMessages` component into a Langflow flow:

1. **Add the `DiscordGetChannelMessages` component** to your flow.
2. **Configure the component** by providing:
   - `Token`: The Discord Application Token (available from the Discord Developers App page).
   - `ChannelId`: The ID of the channel from which you want to retrieve messages.
   - `Limit`: The limit of the number of messages you want to retrieve, you can use 0 for limitless.
   - `ignoreAttachments`: Ignore attachments when retrieving the messages.
   - `ignoreFileContent`: Will ignore file contents from the retrieved messages (metadata).
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin retrieving messages from a Discord channel.

## Code Block for the `DiscordGetChannelMessages` Component

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

class DiscordGetChannelMessages(CustomComponent):
    display_name = "DiscordGetChannelMessages"
    description = "get the messages of discord's channel"
    field_order = ["token", "channel_id", "limit"]
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
            }, "ignore_attachments": {
                "display_name": "IgnoreAttachments",
                "value": True,
                "advanced": False,
                "required": False,
            }, "ignore_file_content": {
                "display_name": "IgnoreFileContent",
                "value": True,
                "advanced": False,
                "required": False,
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

    def build(self, token: str, channel_id: int, ignore_attachments: Optional[bool], ignore_file_content: Optional[bool],  limit: int) -> str:
        import requests
        body = {"token": token, "limit": limit}
        if ignore_attachments:
            body["ignore_attachments"] = ignore_attachments
        if ignore_file_content:
            body["ignore_file_content"] = ignore_file_content
        resp = requests.post(f"http://discord:7880/api/v1/channels/{channel_id}/get_messages", json=body)
        if resp.status_code == 200:
            print(resp.content, flush=True)
            return loads(resp.content)
        else:
            raise Exception("Timeout exception")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `DiscordGetChannelMessages` component in a Langflow flow with the specified `channelId`, `Token`, `Limit`, `ignoreAttachments`, and `ignoreFileContent`:

<ZoomableImage
  alt="Discord Get Channel Messages Flow"
  sources={{
    light: "img/discord/DiscordGetChannelMessages_flow_example.png",
    dark: "img/discord/DiscordGetChannelMessages_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `DiscordGetChannelMessages` component connects to a text output node to display messages. Ensure you have the correct `channelId` and `Token` for successful operation.

</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">

When using the `DiscordGetChannelMessages` component:

- Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
- Verify the `Token` is correct.
- Ensure the `channelId` used is correct and accessible by the bot.
- Keep your Discord integration token secure.
- Test the setup in a private channel before production deployment.

</Admonition>

## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `DiscordGetChannelMessages` component, consider the following:

- Verify the Discord integration token’s validity and permissions.
- Consult the Discord Developers APP Page for documentation updates.
- Ensure the `channelId` is correct.

</Admonition>