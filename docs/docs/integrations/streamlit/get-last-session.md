
import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Get Last Session of Streamlit

Langflow enhances its functionality with custom components like `StreamlitGetLastSession`. This component retrieves the last session information from a specified Streamlit application.


## Component Functionality

<Admonition type="tip" title="Component Functionality">

The `StreamlitGetLastSession` component allows you to:

- Retrieve last session from a Streamlit server.
- Integrate Streamlit seamlessly into your Langflow workflow.

</Admonition>

## Component Usage

To incorporate the `StreamlitGetLastSession` component into a Langflow flow:

1. **Add the `StreamlitGetLastSession` component** to your flow.
2. **Connect the component** to other nodes in your flow as needed.
3. **Initiate the flow** to begin retrieving the last session from a Streamlit server.

## Code Block for the `StreamlitGetLastSession` Component

```python
from typing import Optional
from langflow import CustomComponent
import subprocess
import sys
import base64
from json import loads, dumps

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    return 1

install("requests")

class StreamlitGetLastSession(CustomComponent):
    display_name = "StreamlitGetLastSession"
    description = "Get the last session of Streamlit"
    field_order = ["input"]
    icon = "Streamlit"

    def build_config(self) -> dict:
        return {
            "input": {
                "display_name": "Input",
                "info": "One more way to connect to the flow",
                "value": None,
                "required": False,
            }
        }

    def build(self, input: Optional[str] = None) -> str:
        import requests
        resp = requests.get(f"http://streamlit:7881/api/v1/sessions/last")
        if resp.status_code == 200:
            return dumps(loads(resp.content)).strip('"')
        else:
            raise Exception("Timeout exception")
```

## Example Usage

<Admonition type="info" title="Example Usage">

Example of using the `StreamlitGetLastSession` component in a Langflow flow:

<ZoomableImage
  alt="Streamlit Get Last Session Flow"
  sources={{
    light: "img/streamlit/StreamlitGetLastSession_flow_example.png",
    dark: "img/streamlit/StreamlitGetLastSession_flow_example_dark.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `StreamlitGetLastSession` component connects to a text output node to display last session.

</Admonition>


## Troubleshooting

<Admonition type="caution" title="Troubleshooting">

If you encounter any issues while using the `StreamlitGetLastSession` component, consider the following:

- Consult the Streamlit Developers APP Page for documentation updates.

</Admonition>
