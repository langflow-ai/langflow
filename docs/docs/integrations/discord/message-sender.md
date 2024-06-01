  import Admonition from "@theme/Admonition";
  import ThemedImage from "@theme/ThemedImage";
  import useBaseUrl from "@docusaurus/useBaseUrl";
  import ZoomableImage from "/src/theme/ZoomableImage.js";

  # Message Sender

  Langflow enhances its functionality with custom components like `DiscordMessageSender`. This component sends text messages to a specified Discord channel or thread.

  ## Component Functionality

  <Admonition type="tip" title="Component Functionality">

  The `DiscordMessageSender` component allows you to:

  - Send text messages to a Discord channel or thread.
  - Integrate Discord seamlessly into your Langflow workflow.

  </Admonition>

  ## Component Usage

  To incorporate the `DiscordMessageSender` component into a Langflow flow:

  1. **Add the `DiscordMessageSender` component** to your flow.
  2. **Configure the component** by providing:
     - `Token`: The Discord Application Token (available from the Discord Developers App page).
     - `ChannelId`: The ID of the channel to which you want to send files (can be found by right-clicking the channel with Discord Developer Mode enabled).
     - `Message`: The text message you wish to send.
  3. **Connect the component** to other nodes in your flow as needed.
  4. **Initiate the flow** to begin sending files to a Discord channel or thread.

  ## Code Block for the `DiscordMessageSender` Component

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

  class DiscordMessageSender(CustomComponent):
      display_name = "DiscordMessageSender"
      description = "Send a message to a discord channel"
      field_order = ["token", "channel_id", "message"]
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
              }, "message": {
                  "display_name": "Message",
                  "advanced": False,
                  "required": True,
              }
          }

      def build(self, token: str, channel_id: int, message: str) -> str:
          import requests
          resp = requests.post(
              f"http://discord:7880/api/v1/channels/{channel_id}/send_message",
              json={
                  "token": token,
                  "message": message
          })
          if resp.status_code == 200:
              return "Sent successfully message:" + message
          else:
              if isinstance(resp.content, str):
                  raise Exception(resp.content)

                  raise Exception(resp.content)
  ```

  ## Example Usage

  <Admonition type="info" title="Example Usage">

  Example of using the `DiscordMessageSender` component in a Langflow flow with the specified `ChannelId`, `Token` and `Message`:

  <ZoomableImage
    alt="Discord Message Sender Flow"
    sources={{
      light: "img/discord/DiscordMessageSender_flow_example.png",
      dark: "img/discord/DiscordMessageSender_flow_example_dark.png",
    }}
    style={{ width: "100%", margin: "20px 0" }}
  />

  In this example, the `DiscordMessageSender` component is connected to a file record and sends it to a channel through the component, then continues the flow node with the previous message. Ensure you have the correct `ChannelId`, `Token`, and `Message` for successful operation.

  </Admonition>

  ## Best Practices

  <Admonition type="tip" title="Best Practices">

  When using the `DiscordMessageSender` component:

  - Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
  - Verify the `Token` is correct.
  - Ensure the `ChannelId` used is correct and accessible by the bot.
  - Ensure the `Message` field is set.
  - Keep your Discord integration token secure.
  - Test the setup in a private channel before production deployment.

  </Admonition>

  ## Troubleshooting

  <Admonition type="caution" title="Troubleshooting">

  If you encounter any issues while using the `DiscordMessageSender` component, consider the following:

  - Verify the Discord integration token’s validity and permissions.
  - Consult the Discord Developers APP Page for documentation updates.
  - Ensure the `ChannelId` is correct.

  </Admonition>