# Listen

Langflow enhances its functionality with custom components like `Listen`. This component listen for message of a self hosted Streamlit application.

## Prerequisites

1. **Setting up a Streamlit App**: Follow the guide [Setting up a Streamlit App](./setup) to set up a Streamlit application in your workspace.


## Component Functionality

:::tip Component Functionality

The `Listen` component allows you to:

- Listen for the next message from a Streamlit chat.
- Defines the layout of Streamlit server.

:::

## Component Usage

To incorporate the `Listen` component into a Langflow flow:

1. **Add the `Listen` component** to your flow.
2. **Configure the component** by providing:
   - `Timeout`: The time limit provided to wait for the next message.
   - `WelcomeMessage`: The message that will be displayed on the begin of each chat.
   - `InputMessage`: The placeholder that will be displayed on the user input field of each chat.
   - `WriteSpeed`: The word rate speed that the AI messages will be written(seconds).
   - `AIAvatar`: The avatar that will be used by ai role.
   - `UserAvatar`: The avatar that will be used by user role.
3. **Connect the component** to other nodes in your flow as needed.
4. **Initiate the flow** to begin retrieving the messages of session from a Streamlit server.

## Code Block for the `Listen` Component

```python
from typing import Optional
from langflow.custom import Component
from langflow.schema.message import Message, Data
from langflow.inputs import MessageTextInput, IntInput, StrInput, FloatInput
from json import loads, dumps


class Listen(Component):
    display_name = "Listen"
    description = "Retrieve the next Streamlit chat message and mount the chat template (webhook)."
    icon = "Streamlit"
    response = None

    inputs = [
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout in seconds",
            placeholder="Enter the listen timeout",
            value=120,
            required=True
        ),
        StrInput(
            name="welcome_msg",
            display_name="Welcome Message",
            info="Message that will be displayed at begin of every chat.",
            value="Welcome!",
            required=True,
            advanced=True
        ),
        StrInput(
            name="input_msg",
            display_name="Input Message",
            info="A Text Input Placeholder for send message box.",
            value="Enter you message",
            required=True,
            advanced=True
        ),
        FloatInput(
            name="write_speed",
            display_name="Write Speed",
            info="The delay time between writing each word.",
            value=0.2,
            required=True,
            advanced=True
        ),
        MessageTextInput(
            name="ai_avatar",
            display_name="AI Avatar",
            info="Icon to be used for AI messages. It must be an emoji!",
            value="🤖",
            required=False,
            advanced=True
        ),
        MessageTextInput(
            name="user_avatar",
            display_name="User Avatar",
            info="Icon to be used for user messages. It must be an emoji!",
            value="",
            required=False,
            advanced=True
        ),
        IntInput(
            name="port",
            display_name="Port",
            info="Streamlit API Port",
            value=7881,
            required=True,
            advanced=True
        ),
        StrInput(
            name="hostname",
            display_name="hostname",
            info="IP or hostname of Streamlit API",
            value="localhost",
            required=True,
            advanced=True
        )
    ]

    outputs = [
        Output(display_name="Session ID", name="session_id", method="session_id_response"),
        Output(display_name="Message Content", name="message_content", method="message_content_response"),
        Output(display_name="History", name="chat history", method="chat_history_response"),
    ]

    def get_api_response(self):
        import requests
        body = {
            "welcome_msg": self.welcome_msg,
            "input_msg": self.input_msg,
            "write_speed": self.write_speed,
        }
        if self.ai_avatar: body["ai_avatar"] = self.ai_avatar
        if self.user_avatar: body["user_avatar"] = self.user_avatar
        resp = requests.post(f"http://{self.hostname}:{self.port}/api/v1/chats", json=body)
        resp = requests.get(f"http://{self.hostname}:{self.port}/api/v1/listen/message?timeout={self.timeout}")
        if resp.status_code == 200:
            self.response = loads(resp.content)
            return self.response
        else:
            raise Exception("Timeout exception")

    def session_id_response(self) -> Message:
        if self.response is not None:
            return Message(
                text=self.response["session_id"],
            )
        return Message(
            text=self.get_api_response()["session_id"],
        )

    def message_content_response(self) -> Message:
        if self.response is not None:
            return Message(
                text=self.response["content"],
                sender="User",
            )
        return Message(
            text=self.get_api_response()["content"],
        )

    def chat_history_response(self) -> Data:
        if self.response is not None:
            return self.response["history"]
        return self.get_api_response()["history"]
```

## Example Usage

:::info Example Usage

Example of using the `Listen` component in a Langflow flow:

![](./767267152.png)

In this example, the `Listen` component connects to a text output node to display the listened message.

:::


## Troubleshooting

:::caution Troubleshooting

If you encounter any issues while using the `Listen` component, consider the following:

- Ensure the provided time limit is correct and the Streamlit application is accessible.
- Consult the Streamlit Developers APP Page for documentation updates.
- Verify the welcome message is filled correctly.
- Verify the input message is filled correctly.
- Ensure the provided write speed field is set appropriately.
- Ensure the provided avatar icons are emojis.
- Consult the Streamlit Developers APP Page for documentation updates.

:::
