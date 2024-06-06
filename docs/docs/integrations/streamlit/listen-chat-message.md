
import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Streamlit Listen Chat Message

Langflow enhances its functionality with custom components like `StreamlitListenChatMessage`. This component listen for message of a specified Streamlit application.


## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `StreamlitListenChatMessage` component allows you to:

- Listen for the next message from a Streamlit server.
- Integrate Streamlit seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `StreamlitListenChatMessage` component into a Langflow flow:

1. **Add the `StreamlitListenChatMessage` component** to your flow.
2. **Configure the component** by providing:
   - `Timeout`: The time limit provided to wait for the next message.
2. **Connect the component** to other nodes in your flow as needed.
3. **Initiate the flow** to begin retrieving the messages of session from a Streamlit server.

## Code Block for the `StreamlitListenChatMessage` Component

```python
from typing import Optional
from langflow import CustomComponent
import subprocess
import sys
from json import loads, dumps

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class StreamlitListenChatMessage(CustomComponent):
    display_name = "StreamlitListenChatMessage"
    description = "Retrieve the next Streamlit chat message (webhook)."
    field_order = ["timeout", "message"]
    icon = "Streamlit"

    def build_config(self) -> dict:
        return {
            "timeout": {
                "display_name": "timeout",
                "info": "Timeout in seconds",
                "value": 1*60,
                "required": False,
            },"message": {
                "display_name": "Message",
                "info": "One more way to connect to the flow",
                "value": None,
                "required": False,
            }
        }

    def build(self, timeout: int, message: Optional[str] = None) -> str:
        import requests
        resp = requests.get(f"http://streamlit:7881/api/v1/listen/message?timeout={timeout}")
        if resp.status_code == 200:
            return dumps(loads(resp.content))
        else:
            raise Exception("Timeout exception")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `StreamlitListenChatMessage` component in a Langflow flow:

<ZoomableImage
  alt="Streamlit Get Session Messages Flow"
  sources={{
    light: "img/streamlit/StreamlitListenChatMessage_flow_example.png",
    dark: "img/streamlit/StreamlitListenChatMessage_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `StreamlitListenChatMessage` component connects to a text output node to display the listened message.

</Admonition>


## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `StreamlitListenChatMessage` component, consider the following:

- Ensure the provided time limit is correct and the Streamlit application is accessible.
- Consult the Streamlit Developers APP Page for documentation updates.

</Admonition>
