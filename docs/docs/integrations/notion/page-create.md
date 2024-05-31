import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Page Create

The `NotionPageCreator` component creates pages in a Notion database. It provides a convenient way to integrate Notion page creation into your Langflow workflows.

[Notion Reference](https://developers.notion.com/reference/patch-block-children)

<Admonition type="tip" title="Component Functionality">
The `NotionPageCreator` component enables you to:
- Create new pages in a specified Notion database
- Set custom properties for the created pages
- Retrieve the ID and URL of the newly created pages
</Admonition>

## Component Usage

To use the `NotionPageCreator` component in a Langflow flow, follow these steps:

1. Add the `NotionPageCreator` component to your flow.
2. Configure the component by providing the required inputs:
   - `database_id`: The ID of the Notion database where the pages will be created.
   - `notion_secret`: The Notion integration token for authentication.
   - `properties`: The properties of the new page, specified as a JSON string.
3. Connect the component to other components in your flow as needed.
4. Run the flow to create Notion pages based on the configured inputs.

## Component Python Code

```python
import json
from typing import Optional

import requests
from langflow.custom import CustomComponent


class NotionPageCreator(CustomComponent):
    display_name = "Create Page [Notion]"
    description = "A component for creating Notion pages."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-create"
    icon = "NotionDirectoryLoader"

    def build_config(self):
        return {
            "database_id": {
                "display_name": "Database ID",
                "field_type": "str",
                "info": "The ID of the Notion database.",
            },
            "notion_secret": {
                "display_name": "Notion Secret",
                "field_type": "str",
                "info": "The Notion integration token.",
                "password": True,
            },
            "properties": {
                "display_name": "Properties",
                "field_type": "str",
                "info": "The properties of the new page. Depending on your database setup, this can change. E.G: {'Task name': {'id': 'title', 'type': 'title', 'title': [{'type': 'text', 'text': {'content': 'Send Notion Components to LF', 'link': null}}]}}",
            },
        }

    def build(
        self,
        database_id: str,
        notion_secret: str,
        properties: str = '{"Task name": {"id": "title", "type": "title", "title": [{"type": "text", "text": {"content": "Send Notion Components to LF", "link": null}}]}}',
    ) -> str:
        if not database_id or not properties:
            raise ValueError("Invalid input. Please provide 'database_id' and 'properties'.")

        headers = {
            "Authorization": f"Bearer {notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        data = {
            "parent": {"database_id": database_id},
            "properties": json.loads(properties),
        }

        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)

        if response.status_code == 200:
            page_id = response.json()["id"]
            self.status = f"Successfully created Notion page with ID: {page_id}\n {str(response.json())}"
            return response.json()
        else:
            error_message = f"Failed to create Notion page. Status code: {response.status_code}, Error: {response.text}"
            self.status = error_message
            raise Exception(error_message)
```

## Example Usage

<Admonition type="info" title="Example Usage">
Here's an example of how to use the `NotionPageCreator` component in a Langflow flow:

<ZoomableImage
alt="NotionPageCreator Flow Example"
sources={{
    light: "img/notion/NotionPageCreator_flow_example.png",
    dark: "img/notion/NotionPageCreator_flow_example_dark.png",
  }}
style={{ width: "100%", margin: "20px 0" }}
/>
</Admonition>

## Best Practices

When using the `NotionPageCreator` component, consider the following best practices:

- Ensure that you have a valid Notion integration token with the necessary permissions to create pages in the specified database.
- Properly format the `properties` input as a JSON string, matching the structure and field types of your Notion database.
- Handle any errors or exceptions that may occur during the page creation process and provide appropriate error messages.
- To avoid the hassle of messing with JSON, we recommend using the LLM to create the JSON for you as input.

The `NotionPageCreator` component simplifies the process of creating pages in a Notion database directly from your Langflow workflows. By leveraging this component, you can seamlessly integrate Notion page creation functionality into your automated processes, saving time and effort. Feel free to explore the capabilities of the `NotionPageCreator` component and adapt it to suit your specific requirements.

## Troubleshooting

If you encounter any issues while using the `NotionPageCreator` component, consider the following:

- Double-check that the `database_id` and `notion_secret` inputs are correct and valid.
- Verify that the `properties` input is properly formatted as a JSON string and matches the structure of your Notion database.
- Check the Notion API documentation for any updates or changes that may affect the component's functionality.
