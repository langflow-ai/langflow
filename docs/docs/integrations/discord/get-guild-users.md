import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Get Guild Users

Langflow enhances its functionality with custom components like `DiscordGetGuildUsers`. This component retrieves information about users in a specified Discord guild.

## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `DiscordGetGuildUsers` component allows you to:

- Retrieve detailed information about all users within a Discord guild.
- Integrate Discord seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `DiscordGetGuildUsers` component into a Langflow flow:

1. **Add the `DiscordGetGuildUsers` component** to your flow.
2. **Configure the component** by providing:
  - `Token`: The Discord Application Token (available from the Discord Developers App page).
  - `GuildId`: The ID of the guild from which you want to retrieve user information.
  - `ChannelId`: The ID of the channel from which you want the data.
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin retrieving information about users in a Discord guild.

## Code Block for the `DiscordGetGuildUsers` Component

```python
from langflow import CustomComponent
from langflow.field_typing import Data

from langflow import CustomComponent
import subprocess
import sys
import base64
from tempfile import NamedTemporaryFile
from json import loads

def install(package):
   subprocess.check_call([sys.executable, "-m", "pip", "install", package])
   return 1

install("requests")

class DiscordGetGuildUsers(CustomComponent):
   display_name = "DiscordGetGuildUsers"
   description = "get the users of discord's guild"
   field_order = ["token", "guild_id", "channel_id"]
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
           }, "channel_id": {
               "display_name": "ChannelId",
               "advanced": False,
               "info": "The channel of guild can be used get guild users",
               "required": False,
           }
       }

   def build(self, token: str, guild_id: int, channel_id: int) -> str:
       import requests
       print(guild_id, channel_id)
       resp = requests.post("http://discord:7880/api/v1/get_guild_users", json={"token": token, "guild_id": guild_id, "channel_id": channel_id})
       if resp.status_code == 200:
           return loads(resp.content)
       elif resp.status_code == 422:
           raise Exception(loads(resp.content)["detail"][0]["msg"])
       else:
           raise Exception(str(resp.content))
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `DiscordGetGuildUsers` component in a Langflow flow with the specified `GuildId`, `Token`, and `ChannelId`:

<ZoomableImage
 alt="Discord Get Guild Users Flow"
 sources={{
   light: "img/discord/DiscordGetGuildUsers_flow_example.png",
   dark: "img/discord/DiscordGetGuildUsers_flow_example_dark.png",
 }}
 style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `DiscordGetGuildUsers` component connects to a text output node to display user information. Ensure you have the correct `GuildId`, `ChannelId`, and `Token` for successful operation.

</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">

When using the `DiscordGetGuildUsers` component:

- Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
- Verify the `Token` is correct.
- Ensure the `GuildId` used is correct and accessible by the bot.
- Ensure the `ChannelId` used is correct and accessible by the bot.
- Keep your Discord integration token secure.
- Test the setup in a private channel before production deployment.

</Admonition>

## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `DiscordGetGuildUsers` component, consider the following:

1. Verify the Discord integration token’s validity and permissions.
2. Consult the Discord Developers APP Page for documentation updates.
3. Ensure the `GuildId` is correct.
4. Ensure the `ChannelId` is correct.

</Admonition>