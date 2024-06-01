import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Get Guild Channels

Langflow enhances its functionality with custom components like `DiscordGetGuildChannels`. This component retrieves information about channels in a specified Discord server.

## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `DiscordGetGuildChannels` component allows you to:

- Retrieve detailed information about all channels (if allowed to the bot) within a Discord server.
- Integrate Discord seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `DiscordGetGuildChannels` component into a Langflow flow:

1. **Add the `DiscordGetGuildChannels` component** to your flow.
2. **Configure the component** by providing:
- `Token`: The Discord Application Token (available from the Discord Developers App page).
- `Type`: The channel types you want to retrieve (audio or message).
- `GuildId`: The ID of the server from which you want to retrieve channel information.
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin retrieving information about channels in a Discord server.

## Code Block for the `DiscordGetGuildChannels` Component

```python
from langflow import CustomComponent
from langflow.field_typing import Data

from langflow import CustomComponent
import subprocess
import sys
import base64
from tempfile import NamedTemporaryFile
from json import loads
from typing import Optional

def install(package):
subprocess.check_call([sys.executable, "-m", "pip", "install", package])
return 1

install("requests")

class DiscordGetGuildChannels(CustomComponent):
display_name = "DiscordGetGuildChannels"
description = "get the users of discord's channels"
field_order = ["token", "guild_id", "filter"]
icon = "Discord"

def build_config(self) -> dict:
    return {
        "token": {
            "display_name": "Token",
            "advanced": False,
            "password": True,
            "required": True,
        }, "guild_id": {
            "display_name": "GuildId",
            "advanced": False,
            "required": True,
        }, "filter": {
            "display_name": "Type",
            "info": "filter by type of channel",
            "options": [
                "Text",
                "Category",
                "Voice",
                ""
            ],
            "required": False,
            "advanced": False,
            "value": None,
        }
    }

def build(self, token: str, guild_id: int, filter: Optional[str] = None) -> dict:
    import requests
    body = {"token": token}
    if filter:
        body["type"] = filter
    resp = requests.post(f"http://discord:7880/api/v1/guilds/{guild_id}/get_channels", json=body)
    if resp.status_code == 200:
        return loads(resp.content)
    elif resp.status_code == 422:
        raise Exception(loads(resp.content)["detail"][0]["msg"])
    else:
        raise Exception(str(resp.content))
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `DiscordGetGuildChannels` component in a Langflow flow with the specified `GuildId`, `Token`, and `Type`:

<ZoomableImage
alt="Discord Get Guild Channels Flow"
sources={{
light: "img/discord/DiscordGetGuildChannels_flow_example.png",
dark: "img/discord/DiscordGetGuildChannels_flow_example_dark.png",
}}
style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `DiscordGetGuildChannels` component connects to a text output node to display channel information. Ensure you have the correct `GuildId` and `Token` for successful operation.

</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">

When using the `DiscordGetGuildChannels` component:

- Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
- Verify the `Token` is correct.
- Ensure the `GuildId` used is correct and accessible by the bot.
- Keep your Discord integration token secure.
- Test the setup in a private channel before production deployment.

</Admonition>

## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `DiscordGetGuildChannels` component, consider the following:

- Verify the Discord integration token’s validity and permissions.
- Consult the Discord Developers APP Page for documentation updates.
- Ensure the `GuildId` is correct.

</Admonition>