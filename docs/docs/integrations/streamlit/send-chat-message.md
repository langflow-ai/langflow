
import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Streamlit Send Chat Message

Langflow enhances its functionality with custom components like `StreamlitSendChatMessage`. This component sends message the provided session of a specified Streamlit application.


## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `StreamlitSendChatMessage` component allows you to:

- Retrieve messages of session from a Streamlit server.
- Integrate Streamlit seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `StreamlitSendChatMessage` component into a Langflow flow:

1. **Add the `StreamlitSendChatMessage` component** to your flow.
2. **Configure the component** by providing:
   - `SessionId`: The ID of the session you want to interact with.
   - `Role`: The role that will be used to send the message.
2. **Connect the component** to other nodes in your flow as needed.
3. **Initiate the flow** to begin retrieving the messages of session from a Streamlit server.

## Code Block for the `StreamlitSendChatMessage` Component

```python
from langflow import CustomComponent
import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class StreamlitSendChatMessage(CustomComponent):
    display_name = "StreamlitSendChatMessage"
    description = "Send a Streamlit chat message (webhook)."
    field_order = ["session_id", "role", "message"]
    icon = "Streamlit"

    def build_config(self) -> dict:
        return {
            "session_id": {
                "display_name": "SessionId",
                "advanced": False,
                "required": True,
            },"role": {
                "display_name": "Role",
                "advanced": False,
                "options": ["ai", "user"],
                "value": "ai",
                "required": True,
            },"message": {
                "display_name": "Message",
                "advanced": False,
                "required": True,
            }
        }

    def build(self, session_id: str, message: str, role: str = "ai") -> str:
        import requests
        resp = requests.post(f"http://streamlit:7881/api/v1/sessions/{session_id}/messages", json={"role": role, "content": message})
        if resp.status_code == 200:
            return resp.content
        else:
            raise Exception("Timeout exception")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `StreamlitSendChatMessage` component in a Langflow flow:

<ZoomableImage
  alt="Streamlit Send Chat Message Flow"
  sources={{
    light: "img/streamlit/StreamlitSendChatMessage_flow_example.png",
    dark: "img/streamlit/StreamlitSendChatMessage_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `StreamlitSendChatMessage` component receives an text message as input and sends to streamlit chat session.

</Admonition>


## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `StreamlitSendChatMessage` component, consider the following:

- Ensure the provided session ID is correct and the Streamlit application is accessible.
- Ensure the provided role is set appropriately.
- Consult the Streamlit Developers APP Page for documentation updates.

</Admonition>
