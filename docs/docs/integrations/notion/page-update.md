import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Page Update

The `NotionPageUpdate` component updates the properties of a Notion page. It provides a convenient way to integrate updating Notion page properties into your Langflow workflows.

[Notion Reference](https://developers.notion.com/reference/patch-page)

## Component Usage

To use the `NotionPageUpdate` component in your Langflow flow:

1. Drag and drop the `NotionPageUpdate` component onto the canvas.
2. Double-click the component to open its configuration.
3. Provide the required parameters as defined in the component's `build_config` method.
4. Connect the component to other nodes in your flow as needed.

## Component Python Code

```python
import json
import requests
from typing import Dict, Any

from langflow import CustomComponent
from langflow.schema import Record


class NotionPageUpdate(CustomComponent):
    display_name = "Update Page Property [Notion]"
    description = "Update the properties of a Notion page."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-update"
    icon = "NotionDirectoryLoader"

    def build_config(self):
        return {
            "page_id": {
                "display_name": "Page ID",
                "field_type": "str",
                "info": "The ID of the Notion page to update.",
            },
            "properties": {
                "display_name": "Properties",
                "field_type": "str",
                "info": "The properties to update on the page (as a JSON string).",
                "multiline": True,
            },
            "notion_secret": {
                "display_name": "Notion Secret",
                "field_type": "str",
                "info": "The Notion integration token.",
                "password": True,
            },
        }

    def build(
        self,
        page_id: str,
        properties: str,
        notion_secret: str,
    ) -> Record:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        headers = {
            "Authorization": f"Bearer {notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",  # Use the latest supported version
        }

        try:
            parsed_properties = json.loads(properties)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON format for properties") from e

        data = {
            "properties": parsed_properties
        }

        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()

        updated_page = response.json()

        output = "Updated page properties:\n"
        for prop_name, prop_value in updated_page["properties"].items():
            output += f"{prop_name}: {prop_value}\n"

        self.status = output
        return Record(data=updated_page)
```

Let's break down the key parts of this component:

- The `build_config` method defines the configuration fields for the component. It specifies the required parameters and their properties, such as display names, field types, and any additional information or validation.

- The `build` method contains the main logic of the component. It takes the configured parameters as input and performs the necessary operations to update the properties of a Notion page.

- The component interacts with the Notion API to update the page properties. It constructs the API URL, headers, and request data based on the provided parameters.

- The processed data is returned as a `Record` object, which can be connected to other components in the Langflow flow. The `Record` object contains the updated page data.

- The component also stores the updated page properties in the `status` attribute for logging and debugging purposes.

## Example Usage

<Admonition type="info" title="Example Usage">
Here's an example of how to use the `NotionPageUpdate` component in a Langflow flow using:

<ZoomableImage
alt="NotionPageUpdate Flow Example"
sources={{
    light: "img/notion/NotionPageUpdate_flow_example.png",
    dark: "img/notion/NotionPageUpdate_flow_example_dark.png",
  }}
style={{ width: "100%", margin: "20px 0" }}
/>
</Admonition>

## Best Practices

When using the `NotionPageUpdate` component, consider the following best practices:

- Ensure that you have a valid Notion integration token with the necessary permissions to update page properties.
- Handle edge cases and error scenarios gracefully, such as invalid JSON format for properties or API request failures.
- We recommend using an LLM to generate the inputs for this component, to allow flexibilty

By leveraging the `NotionPageUpdate` component in Langflow, you can easily integrate updating Notion page properties into your language model workflows and build powerful applications that extend Langflow's capabilities.

## Troubleshooting

If you encounter any issues while using the `NotionPageUpdate` component, consider the following:

- Double-check that you have correctly configured the component with the required parameters, including the page ID, properties JSON, and Notion integration token.
- Verify that your Notion integration token has the necessary permissions to update page properties.
- Check the Langflow logs for any error messages or exceptions related to the component, such as invalid JSON format or API request failures.
- Consult the [Notion API Documentation](https://developers.notion.com/reference/patch-page) for specific troubleshooting steps or common issues related to updating page properties.
