  import Admonition from "@theme/Admonition";
  import ThemedImage from "@theme/ThemedImage";
  import useBaseUrl from "@docusaurus/useBaseUrl";
  import ZoomableImage from "/src/theme/ZoomableImage.js";

  # Bot Name

  Langflow enhances its functionality with custom components like `DiscordBotName`. This component retrieves the name of a Discord bot using the specified token.

  ## Component Functionality

  <Admonition type="tip" title="Component Functionality">

  The `DiscordBotName` component allows you to:

  - Retrieve the name of a Discord bot using a secure token.
  - Integrate Discord seamlessly into your Langflow workflow.

  </Admonition>

  ## Component Usage

  To incorporate the `DiscordBotName` component into a Langflow flow:

  1. **Add the `DiscordBotName` component** to your flow.
  2. **Configure the component** by providing:
     - `Token`: The Discord Application Token (available from the Discord Developers App page).
  3. **Connect the component** to other nodes in your flow as needed.
  4. **Initiate the flow** to begin sending files to a Discord channel or thread.

  ## Code Block for the `DiscordBotName` Component

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

  class DiscordBotName(CustomComponent):
      display_name = "DiscordBotName"
      description = "get discord bot name"
      field_order = ["token"]
      icon = "Discord"

      def build_config(self) -> dict:
          return {
              "token": {
                  "display_name": "Token",
                  "advanced": False,
                  "password": True,
                  "required": True,
              }
          }

      def build(self, token: str) -> str:
          import requests
          resp = requests.post("http://localhost:7880/api/v1/bot_name", json={"token": token})
          if resp.status_code == 200:
              return resp.content
          else:
              raise Exception("Timeout exception")
  ```

  ## Example Usage

  <Admonition type="info" title="Example Usage">

  Example of using the `DiscordBotName` component in a Langflow flow with the specified `Token`:

  <ZoomableImage
    alt="Discord Bot Name Flow"
    sources={{
      light: "img/discord/DiscordBotName_flow_example.png",
      dark: "img/discord/DiscordBotName_flow_example_dark.png",
    }}
    style={{ width: "100%", margin: "20px 0" }}
  />

  In this example, the `DiscordBotName` component is connected to a file record and sends it to a channel through the component, then continues the flow node with the previous message. Ensure you have the correct `Token` for successful operation.

  </Admonition>

  ## Best Practices

  <Admonition type="tip" title="Best Practices">

  When using the `DiscordBotName` component:

  - Ensure the bot has the necessary permissions as outlined on the Discord APP Developers Page.
  - Verify the `Token` is correct.
  - Keep your Discord integration token secure.
  - Test the setup in a private channel before production deployment.

  </Admonition>

  ## Troubleshooting

  <Admonition type="caution" title="Troubleshooting">

  If you encounter any issues while using the `DiscordBotName` component, consider the following:

  - Verify the Discord integration token’s validity and permissions.
  - Consult the Discord Developers APP Page for documentation updates.

  </Admonition>