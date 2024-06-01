import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Image Sender

Langflow enhances its functionality with custom components like `DiscordImageSender`. This component sends images to a specified Discord channel or thread.

## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `DiscordImageSender` component allows you to:

- Send images to a Discord channel or thread.
- Integrate Discord seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `DiscordImageSender` component into a Langflow flow:

1. **Add the `DiscordImageSender` component** to your flow.
2. **Configure the component** by providing:
   - `Token`: The Discord Application Token (available from the Discord Developers App page).
   - `ChannelId`: The ID of the channel to which you want to send images (can be found by right-clicking the channel with Discord Developer Mode enabled).
   - `File`: The record of the file you want to send.
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin sending images to a Discord channel or thread.

## Code Block for the `DiscordImageSender` Component

```python
from typing import Optional
from langflow import CustomComponent
from langflow.field_typing import Data
from langflow.schema import Record
import subprocess
import sys
import base64
import re

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class DiscordImageSender(CustomComponent):
    display_name = "DiscordImageSender"
    description = "Send image to discord's channel"
    field_order = ["token", "channel_id", "file"]
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
            }, "file": {
                "display_name": "File",
                "advanced": False,
                "required": True,
            }
        }

    def build(self, token: str, channel_id: int, file: Record) -> str:
        import requests
        filename = re.findall(r"(?:(?:\/)|(?:\\))([a-zA-Z\d ._]{0,40})", file.file_path)[-1]

        body = {
            "token": token,
            "type": file.text_key,
            "filename": filename,
            "data": file.data,
        }
        resp = requests.post(
            f"http://discord:7880/api/v1/channels/{channel_id}/send_message",
            json=body)
        if resp.status_code == 200:
            return "Sent record successfully"
        else:
            if isinstance(resp.content, str):
                raise Exception(resp.content)
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `DiscordImageSender` component in a Langflow flow with the specified `ChannelId` and `Token`:

<ZoomableImage
  alt="Discord Image Sender Flow"
  sources={{
    light: "img/discord/DiscordImageSender_flow_example.png",
    dark: "img/discord/DiscordImageSender_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `DiscordImageSender` component connects to a text output node to send images. Ensure you have the correct `ChannelId`, `Token`, and a valid `File` Record for successful operation.

</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">

When using the `DiscordImageSender` component:

- Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
- Verify the `Token` is correct.
- Ensure the `ChannelId` used is correct and accessible by the bot.
- Ensure you are passing a valid `File` Record.
- Keep your Discord integration token secure.
- Test the setup in a private channel before production deployment.

</Admonition>

## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `DiscordImageSender` component, consider the following:

- Verify the Discord integration token’s validity and permissions.
- Consult the Discord Developers APP Page for documentation updates.
- Ensure the `ChannelId` is correct.

</Admonition>