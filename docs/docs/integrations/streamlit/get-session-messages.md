import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Streamlit Get Session Messages

Langflow enhances its functionality with custom components like `StreamlitGetSessionMessages`. This component retrieves all messages from the latest session of a specified Streamlit application.


## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `StreamlitGetSessionMessages` component allows you to:

- Retrieve messages of session from a Streamlit server.
- Integrate Streamlit seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `StreamlitGetSessionMessages` component into a Langflow flow:

1. **Add the `StreamlitGetSessionMessages` component** to your flow.
2. **Configure the component** by providing:
   - `SessionId`: The ID of the session from which you want to retrieve messages.
   - `Limit`: The limit of messages you want to retrieve, 0 means limitless.
2. **Connect the component** to other nodes in your flow as needed.
3. **Initiate the flow** to begin retrieving the messages of session from a Streamlit server.

## Code Block for the `StreamlitGetSessionMessages` Component

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

class StreamlitGetSessionMessages(CustomComponent):
    display_name = "StreamlitGetSessionMessages"
    description = "Retrieve the messages from the Streamlit session."
    field_order = ["session_id", "limit", "message"]
    icon = "Streamlit"

    def build_config(self) -> dict:
        return {
            "session_id": {
                "display_name": "SessionId",
                "info": "The streamlit sessionID",
                "required": True,
            }, "limit": {
                "display_name": "Limit",
                "info": "The limit of messages returned, 0 means limitless",
                "required": True,
            }, "message": {
                "display_name": "Message",
                "info": "One more way to connect to the flow",
                "value": None,
                "required": False,
            }
        }

    def build(self, session_id: str, limit: int = 0, message: Optional[str] = None) -> str:
        import requests
        resp = requests.get(f"http://streamlit:7881/api/v1/sessions/{session_id}/messages?limit={limit}")
        if resp.status_code == 200:
            return dumps(loads(resp.content))
        else:
            raise Exception("Timeout exception")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `StreamlitGetSessionMessages` component in a Langflow flow:

<ZoomableImage
  alt="Streamlit Get Session Messages Flow"
  sources={{
    light: "img/streamlit/StreamlitGetSessionMessages_flow_example.png",
    dark: "img/streamlit/StreamlitGetSessionMessages_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `StreamlitGetSessionMessages` component connects to a text output node to display messages of session.

</Admonition>


## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `StreamlitGetSessionMessages` component, consider the following:

- Ensure the provided session ID is correct and the Streamlit application is accessible.
- Verify that the limit parameter is set appropriately (0 means limitless).
- Consult the Streamlit Developers APP Page for documentation updates.

</Admonition>
