
import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Streamlit Send Chat Message

Langflow enhances its functionality with custom components like `StreamlitChatTemplate`. This component set the chat layout to a specified Streamlit application.


## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `StreamlitChatTemplate` component allows you to:

- Defines the layout of Streamlit server.
- Integrate Streamlit seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `StreamlitChatTemplate` component into a Langflow flow:

1. **Add the `StreamlitChatTemplate` component** to your flow.
2. **Configure the component** by providing:
   - `WelcomeMessage`: The message that will be displayed on the begin of each chat.
   - `InputMessage`: The placeholder that will be displayed on the user input field of each chat.
   - `WriteSpeed`: The word rate speed that the AI messages will be written(seconds).
   - `AIAvatar`: The avatar that will be used by ai role.
   - `UserAvatar`: The avatar that will be used by user role.
2. **Connect the component** to other nodes in your flow as needed.
3. **Initiate the flow** to begin retrieving the messages of session from a Streamlit server.

## Code Block for the `StreamlitChatTemplate` Component

```python
from typing import Optional
from langflow import CustomComponent
import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class StreamlitChatTemplate(CustomComponent):
    display_name = "StreamlitChatTemplate"
    description = "Set up a chat template on Streamlit (webhook)."
    field_order = ["welcome_msg", "input_msg", "write_speed", "ai_avatar", "user_avatar"]
    icon = "Streamlit"

    def build_config(self) -> dict:
        return {
            "welcome_msg": {
                "display_name": "WelcomeMessage",
                "advanced": False,
                "required": True,
            },"input_msg": {
                "display_name": "InputMessage",
                "advanced": False,
                "required": True,
            },"write_speed":{
                "display_name": "WriteSpeed",
                "value": 0.2,
                "advanced": False,
                "required": True,
            },"ai_avatar":{
                "display_name": "AIAvatar",
                "value": None,
                "advanced": False,
                "required": False,
            },"user_avatar":{
                "display_name": "UserAvatar",
                "value": None,
                "advanced": False,
                "required": False,
            },"message": {
                "display_name": "Message",
                "value": None,
                "advanced": False,
                "required": False,
            }
        }

    def build(self, welcome_msg: str, input_msg: str, write_speed: float, ai_avatar: Optional[str] = None, user_avatar: Optional[str] = None, message: Optional[str] = None) -> str:
        import requests
        body = {
            "welcome_msg": welcome_msg,
            "input_msg": input_msg,
            "write_speed": write_speed,
        }
        if ai_avatar: body["ai_avatar"] = ai_avatar
        if user_avatar: body["user_avatar"] = user_avatar
        resp = requests.post("http://streamlit:7881/api/v1/chats", json=body)
        if resp.status_code == 200:
            return resp.content
        else:
            raise Exception("Timeout exception")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `StreamlitChatTemplate` component in a Langflow flow:

<ZoomableImage
  alt="Streamlit Send Chat Message Flow"
  sources={{
    light: "img/streamlit/StreamlitChatTemplate_flow_example.png",
    dark: "img/streamlit/StreamlitChatTemplate_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `StreamlitChatTemplate` component defines the Streamlit web page's visual layout as a chat template.

</Admonition>


## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `StreamlitChatTemplate` component, consider the following:

- Verify the welcome message is filled correctly.
- Verify the input message is filled correctly.
- Ensure the provided write speed field is set appropriately.
- Ensure the provided avatar icons are emojis.
- Consult the Streamlit Developers APP Page for documentation updates.

</Admonition>
