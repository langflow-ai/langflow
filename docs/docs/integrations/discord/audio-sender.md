  import Admonition from "@theme/Admonition";
  import ThemedImage from "@theme/ThemedImage";
  import useBaseUrl from "@docusaurus/useBaseUrl";
  import ZoomableImage from "/src/theme/ZoomableImage.js";

  # Audio Sender

  Langflow enhances its functionality with custom components like `DiscordAudioSender`. This component sends files to a specified Discord channel or thread.

  ## Component Functionality

  <Admonition type="tip" title="Component Functionality">

  The `DiscordAudioSender` component allows you to:

  - Send audios to a Discord channel or thread.
  - Integrate Discord seamlessly into your Langflow workflow.

  </Admonition>

  ## Component Usage

  To incorporate the `DiscordAudioSender` component into a Langflow flow:

  1. **Add the `DiscordAudioSender` component** to your flow.
  2. **Configure the component** by providing:
     - `Token`: The Discord Application Token (available from the Discord Developers App page).
     - `ChannelId`: The ID of the channel to which you want to send files (can be found by right-clicking the channel with Discord Developer Mode enabled).
     - `File`: The record of the audio you want to send.
  3. **Connect the component** to other nodes in your flow as needed.
  4. **Initiate the flow** to begin sending audios to a Discord channel or thread.

  ## Code Block for the `DiscordAudioSender` Component

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
  
  class DiscordAudioSender(CustomComponent):
      display_name = "DiscordAudioSender"
      description = "Send audio file to discord channel"
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
              "is_audio": True,
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

  Example of using the `DiscordAudioSender` component in a Langflow flow with the specified `channelId`, `Token` and `File`:

  <ZoomableImage
    alt="Discord Audio Sender Flow"
    sources={{
      light: "img/discord/DiscordAudioSender_flow_example.png",
      dark: "img/discord/DiscordAudioSender_flow_example_dark.png",
    }}
    style={{ width: "100%", margin: "20px 0" }}
  />

  In this example, the `DiscordAudioSender` component is connected to a file record and sends it to a channel through the component, then continues the flow node with the previous message. Ensure you have the correct `channelId`, `Token`, and a valid `File` Record for successful operation.

  </Admonition>

  ## Best Practices

  <Admonition type="tip" title="Best Practices">

  When using the `DiscordAudioSender` component:

  - Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
  - Verify the `Token` is correct.
  - Ensure the `channelId` used is correct and accessible by the bot.
  - Ensure you have a valid `File` Record (not a corrupted file).
  - Keep your Discord integration token secure.
  - Test the setup in a private channel before production deployment.

  </Admonition>

  ## Troubleshooting

  <Admonition type="caution" title="Troubleshooting">

  If you encounter any issues while using the `DiscordAudioSender` component, consider the following:

  - Verify the Discord integration token’s validity and permissions.
  - Consult the Discord Developers APP Page for documentation updates.
  - Ensure the `channelId` is correct.

  </Admonition>