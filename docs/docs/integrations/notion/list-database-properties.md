import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Database Properties

The `NotionDatabaseProperties` component retrieves properties of a Notion database. It provides a convenient way to integrate Notion database information into your Langflow workflows.

[Notion Reference](https://developers.notion.com/reference/post-database-query)

<Admonition type="tip" title="Component Functionality">
The `NotionDatabaseProperties` component enables you to:
- Retrieve properties of a Notion database
- Access the retrieved properties in your Langflow flows
- Integrate Notion database information seamlessly into your workflows
</Admonition>

## Component Usage

To use the `NotionDatabaseProperties` component in a Langflow flow, follow these steps:

1. Add the `NotionDatabaseProperties` component to your flow.
2. Configure the component by providing the required inputs:
   - `database_id`: The ID of the Notion database you want to retrieve properties from.
   - `notion_secret`: The Notion integration token for authentication.
3. Connect the output of the `NotionDatabaseProperties` component to other components in your flow as needed.

## Component Python code

```python
import requests
from typing import Dict

from langflow import CustomComponent
from langflow.schema import Record


class NotionDatabaseProperties(CustomComponent):
    display_name = "List Database Properties [Notion]"
    description = "Retrieve properties of a Notion database."
    documentation: str = "https://docs.langflow.org/integrations/notion/list-database-properties"
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
        }

    def build(
        self,
        database_id: str,
        notion_secret: str,
    ) -> Record:
        url = f"https://api.notion.com/v1/databases/{database_id}"
        headers = {
            "Authorization": f"Bearer {notion_secret}",
            "Notion-Version": "2022-06-28",  # Use the latest supported version
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        properties = data.get("properties", {})

        record = Record(text=str(response.json()), data=properties)
        self.status = f"Retrieved {len(properties)} properties from the Notion database.\n {record.text}"
        return record
```

## Example Usage

<Admonition type="info" title="Example Usage">
Here's an example of how you can use the `NotionDatabaseProperties` component in a Langflow flow:

<ZoomableImage
alt="NotionDatabaseProperties Flow Example"
sources={{
light: "img/notion/NotionDatabaseProperties_flow_example.png",
dark: "img/notion/NotionDatabaseProperties_flow_example_dark.png",
}}
style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `NotionDatabaseProperties` component retrieves the properties of a Notion database, and the retrieved properties are then used as input for subsequent components in the flow.
</Admonition>

## Best Practices

When using the `NotionDatabaseProperties` component, consider the following best practices:

- Ensure that you have a valid Notion integration token with the necessary permissions to access the desired database.
- Double-check the database ID to avoid retrieving properties from the wrong database.
- Handle potential errors gracefully by checking the response status and providing appropriate error messages.

The `NotionDatabaseProperties` component simplifies the process of retrieving properties from a Notion database and integrating them into your Langflow workflows. By leveraging this component, you can easily access and utilize Notion database information in your flows, enabling powerful integrations and automations.

Feel free to explore the capabilities of the `NotionDatabaseProperties` component and experiment with different use cases to enhance your Langflow workflows!

## Troubleshooting

If you encounter any issues while using the `NotionDatabaseProperties` component, consider the following:

- Verify that the Notion integration token is valid and has the required permissions.
- Check the database ID to ensure it matches the intended Notion database.
- Inspect the response from the Notion API for any error messages or status codes that may indicate the cause of the issue.
