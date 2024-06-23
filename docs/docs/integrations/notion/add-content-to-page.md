import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Add Content To Page

The `AddContentToPage` component converts markdown text to Notion blocks and appends them to a Notion page.

[Notion Reference](https://developers.notion.com/reference/patch-block-children)

The `AddContentToPage` component enables you to:

- Convert markdown text to Notion blocks.
- Append the converted blocks to a specified Notion page.
- Seamlessly integrate Notion content creation into Langflow workflows.

## Component Usage

To use the `AddContentToPage` component in a Langflow flow:

1. **Add the `AddContentToPage` component** to your flow.
2. **Configure the component** by providing:
   - `markdown_text`: The markdown text to convert.
   - `block_id`: The ID of the Notion page/block to append the content.
   - `notion_secret`: The Notion integration token for authentication.
3. **Connect the component** to other nodes in your flow as needed.
4. **Run the flow** to convert the markdown text and append it to the specified Notion page.

## Component Python Code

```python
import json
from typing import Optional

import requests
from langflow.custom import CustomComponent


class NotionPageCreator(CustomComponent):
    display_name = "Create Page [Notion]"
    description = "A component for creating Notion pages."
    documentation: str = "https://docs.langflow.org/integrations/notion/add-content-to-page"
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

Example of using the `AddContentToPage` component in a Langflow flow using Markdown as input:

<ZoomableImage
alt="NotionDatabaseProperties Flow Example"
sources={{
  light: "img/notion/AddContentToPage_flow_example.png",
  dark: "img/notion/AddContentToPage_flow_example.png",
  }}
style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `AddContentToPage` component connects to a `MarkdownLoader` component to provide the markdown text input. The converted Notion blocks are appended to the specified Notion page using the provided `block_id` and `notion_secret`.

## Best Practices

When using the `AddContentToPage` component:

- Ensure markdown text is well-formatted.
- Verify the `block_id` corresponds to the right Notion page/block.
- Keep your Notion integration token secure.
- Test with sample markdown text before production use.

The `AddContentToPage` component is a powerful tool for integrating Notion content creation into Langflow workflows, facilitating easy conversion of markdown text to Notion blocks and appending them to specific pages.

## Troubleshooting

If you encounter any issues while using the `AddContentToPage` component, consider the following:

- Verify the Notion integration token’s validity and permissions.
- Check the Notion API documentation for updates.
- Ensure markdown text is properly formatted.
- Double-check the `block_id` for correctness.
