import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# List Pages

The `NotionListPages` component queries a Notion database with filtering and sorting. It provides a convenient way to integrate Notion database querying capabilities into your Langflow workflows.

[Notion Reference](https://developers.notion.com/reference/post-database-query)

<Admonition type="tip" title="Component Functionality">
 The `NotionListPages` component enables you to:

- Query a Notion database with custom filters and sorting options
- Retrieve specific pages from a Notion database based on the provided criteria
- Integrate Notion database data seamlessly into your Langflow workflows

</Admonition>

## Component Usage

To use the `NotionListPages
` component in a Langflow flow, follow these steps:

1. **Add the `NotionListPages
` component to your flow.**
2. **Configure the component by providing the required parameters:**
   - `notion_secret`: The Notion integration token for authentication.
   - `database_id`: The ID of the Notion database you want to query.
   - `query_payload`: A JSON string containing the filters and sorting options for the query.
3. **Connect the `NotionListPages
` component to other components in your flow as needed.**

## Component Python code

```python
import requests
import json
from typing import Dict, Any, List
from langflow.custom import CustomComponent
from langflow.schema import Record

class NotionListPages(CustomComponent):
    display_name = "List Pages [Notion]"
    description = (
        "Query a Notion database with filtering and sorting. "
        "The input should be a JSON string containing the 'filter' and 'sorts' objects. "
        "Example input:\n"
        '{"filter": {"property": "Status", "select": {"equals": "Done"}}, "sorts": [{"timestamp": "created_time", "direction": "descending"}]}'
    )
    documentation: str = "https://docs.langflow.org/integrations/notion/list-pages"
    icon = "NotionDirectoryLoader"

    field_order = [
        "notion_secret",
        "database_id",
        "query_payload",
    ]

    def build_config(self):
        return {
            "notion_secret": {
                "display_name": "Notion Secret",
                "field_type": "str",
                "info": "The Notion integration token.",
                "password": True,
            },
            "database_id": {
                "display_name": "Database ID",
                "field_type": "str",
                "info": "The ID of the Notion database to query.",
            },
            "query_payload": {
                "display_name": "Database query",
                "field_type": "str",
                "info": "A JSON string containing the filters that will be used for querying the database. EG: {'filter': {'property': 'Status', 'status': {'equals': 'In progress'}}}",
            },
        }

    def build(
        self,
        notion_secret: str,
        database_id: str,
        query_payload: str = "{}",
    ) -> List[Record]:
        try:
            query_data = json.loads(query_payload)
            filter_obj = query_data.get("filter")
            sorts = query_data.get("sorts", [])

            url = f"https://api.notion.com/v1/databases/{database_id}/query"
            headers = {
                "Authorization": f"Bearer {notion_secret}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            }

            data = {
                "sorts": sorts,
            }

            if filter_obj:
                data["filter"] = filter_obj

            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            results = response.json()
            records = []
            combined_text = f"Pages found: {len(results['results'])}\n\n"
            for page in results['results']:
                page_data = {
                    'id': page['id'],
                    'url': page['url'],
                    'created_time': page['created_time'],
                    'last_edited_time': page['last_edited_time'],
                    'properties': page['properties'],
                }

                text = (
                    f"id: {page['id']}\n"
                    f"url: {page['url']}\n"
                    f"created_time: {page['created_time']}\n"
                    f"last_edited_time: {page['last_edited_time']}\n"
                    f"properties: {json.dumps(page['properties'], indent=2)}\n\n"
                )

                combined_text += text
                records.append(Record(text=text, data=page_data))

            self.status = combined_text.strip()
            return records

        except Exception as e:
            self.status = f"An error occurred: {str(e)}"
            return [Record(text=self.status, data=[])]
```

<Admonition type="info" title="Example Usage">

## Example Usage

Here's an example of how you can use the `NotionListPages` component in a Langflow flow and passing to the Prompt component:

<ZoomableImage
alt="NotionListPages
Flow Example"
sources={{
    light: "img/notion/NotionListPages_flow_example.png",
    dark: "img/notion/NotionListPages_flow_example_dark.png",
    }}
style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `NotionListPages` component is used to retrieve specific pages from a Notion database based on the provided filters and sorting options. The retrieved data can then be processed further in the subsequent components of the flow.
</Admonition>

## Best Practices

When using the `NotionListPages
` component, consider the following best practices:

- Ensure that you have a valid Notion integration token with the necessary permissions to query the desired database.
- Construct the `query_payload` JSON string carefully, following the Notion API documentation for filtering and sorting options.

The `NotionListPages
` component provides a powerful way to integrate Notion database querying capabilities into your Langflow workflows. By leveraging this component, you can easily retrieve specific pages from a Notion database based on custom filters and sorting options, enabling you to build more dynamic and data-driven flows.

We encourage you to explore the capabilities of the `NotionListPages
` component further and experiment with different querying scenarios to unlock the full potential of integrating Notion databases into your Langflow workflows.

## Troubleshooting

If you encounter any issues while using the `NotionListPages` component, consider the following:

- Double-check that the `notion_secret` and `database_id` are correct and valid.
- Verify that the `query_payload` JSON string is properly formatted and contains valid filtering and sorting options.
- Check the Notion API documentation for any updates or changes that may affect the component's functionality.
