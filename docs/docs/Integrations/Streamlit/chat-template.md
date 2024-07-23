# Streamlit Chat Template

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
from langflow.custom import Component
#from langflow.api.v1.streamlit import ChatModel, create_chat, listen_message
from langflow.schema.message import Message
from langflow.inputs import MessageTextInput, FloatInput
from json import loads, dumps
import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class StreamlitChatTemplate(Component):
    display_name = "StreamlitChatTemplate"
    description = "Set up a chat template on Streamlit (webhook)."
    field_order = ["welcome_msg", "input_msg", "write_speed", "ai_avatar", "user_avatar"]
    icon = "Streamlit"

    inputs = [
        MessageTextInput(
            name="welcome_msg",
            display_name="WelcomeMessage",
            required=True,
        ),
        MessageTextInput(
            name="input_msg",
            display_name="InputMessage",
            required=True,
        ),
        FloatInput(
            name="write_speed",
            display_name="WriteSpeed",
            value=0.2,
            required=True,
        ),
        MessageTextInput(
            name="ai_avatar",
            display_name="AIAvatar",
            value="🤖",
            info="It must be an emoji",
            required=False,
        ),
        MessageTextInput(
            name="user_avatar",
            display_name="UserAvatar",
            value="",
            required=False,
        ),
        MessageTextInput(
            name="message",
            display_name="Message",
            value="",
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Message:
        import requests
        body = {
            "welcome_msg": self.welcome_msg,
            "input_msg": self.input_msg,
            "write_speed": self.write_speed,
        }
        if self.ai_avatar: body["ai_avatar"] = self.ai_avatar
        if self.user_avatar: body["user_avatar"] = self.user_avatar
        resp = requests.post("http://localhost:7881/api/v1/chats", json=body)
        if resp.status_code == 200:
            return loads(resp.content)
        else:
            raise Exception("Timeout exception")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `StreamlitChatTemplate` component in a Langflow flow:

![](./982136732.png)

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
