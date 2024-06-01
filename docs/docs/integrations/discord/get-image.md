import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Get Image

Langflow enhances its functionality with custom components like `DiscordGetImage`. This component retrieves recent image messages from a specified Discord channel.

## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `DiscordGetImage` component allows you to:

- Retrieve recent image messages from a Discord channel.
- Integrate Discord seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `DiscordGetImage` component into a Langflow flow:

1. **Add the `DiscordGetImage` component** to your flow.
2. **Configure the component** by providing:
   - `Token`: The Discord Application Token (available from the Discord Developers App page).
   - `ChannelId`: The ID of the channel from which you want to retrieve image messages.
   - `Limit`: The limit of images you want to retrieve.
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin retrieving image messages from a Discord channel.

## Code Block for the `DiscordGetImage` Component

```python
from typing import Optional, Any
from langflow import CustomComponent
from langflow.schema import Record
from tempfile import NamedTemporaryFile
import subprocess
import sys
import base64
from json import loads


def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class DiscordGetImage(CustomComponent):
    display_name = "DiscordGetImage"
    description = "get the image from discord's channel"
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
            }, "limit": {
                "display_name": "Limit",
                "value": 20,
                "advanced": False,
                "info": "The value 0 means limitless",
                "required": True,
            }
        }

    def build(self, token: str, channel_id: int,  limit: int) -> Record:
        import requests
        body = {"token": token, "limit": limit, "content_type": ["png", "jpg", "jpeg"]}
        resp = requests.post(f"http://discord:7880/api/v1/channels/{channel_id}/get_messages/last", json=body)
        if resp.status_code == 200:
            file = loads(resp.content)
            print(file.keys())
            tmp_file = NamedTemporaryFile(delete=False, suffix=".png")
            resolved_path = self.resolve_path(tmp_file.name)
            print(tmp_file.name, type(tmp_file.name), type(file))
            with open(tmp_file.name, 'wb') as f:  # Open the file in binary mode
                f.write(base64.b64decode(file["content"]))
            return Record(data={"file_path": resolved_path, "text": file["content"]})
        else:
            raise Exception("Timeout exception")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `DiscordGetImage` component in a Langflow flow with the specified `ChannelId`, `Token`, and `Limit`:

<ZoomableImage
  alt="Discord Get Image Message Flow"
  sources={{
    light: "img/discord/DiscordGetImage_flow_example.png",
    dark: "img/discord/DiscordGetImage_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `DiscordGetImage` component connects to a text output node to display image messages. Ensure you have the correct `ChannelId` and `Token` for successful operation.

</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">

When using the `DiscordGetImage` component:

- Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
- Verify the `Token` is correct.
- Ensure the `ChannelId` used is correct and accessible by the bot.
- Keep your Discord integration token secure.
- Test the setup in a private channel before production deployment.

</Admonition>

## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `DiscordGetImage` component, consider the following:

- Verify the Discord integration token’s validity and permissions.
- Consult the Discord Developers APP Page for documentation updates.
- Ensure the `ChannelId` is correct.

</Admonition>