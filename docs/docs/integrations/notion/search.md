import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Notion Search

The `NotionSearch` component is designed to search all pages and databases that have been shared with an integration in Notion. It provides a convenient way to integrate Notion search capabilities into your Langflow workflows.

[Notion Reference](https://developers.notion.com/reference/search)

<Admonition type="tip" title="Component Functionality">
 The `NotionSearch` component enables you to:

- Search for pages and databases in Notion that have been shared with an integration
- Filter the search results based on object type (pages or databases)
- Sort the search results in ascending or descending order based on the last edited time

</Admonition>

## Component Usage

To use the `NotionSearch` component in a Langflow flow, follow these steps:

1. **Add the `NotionSearch` component to your flow.**
2. **Configure the component by providing the required parameters:**
   - `notion_secret`: The Notion integration token for authentication.
   - `query`: The text to search for in page and database titles.
   - `filter_value`: The type of objects to include in the search results (pages or databases).
   - `sort_direction`: The direction to sort the search results (ascending or descending).
3. **Connect the `NotionSearch` component to other components in your flow as needed.**

## Component Python Code

```python
import requests
from typing import Dict, Any, List
from langflow.custom import CustomComponent
from langflow.schema import Record

class NotionSearch(CustomComponent):
    display_name = "Search Notion"
    description = (
        "Searches all pages and databases that have been shared with an integration."
    )
    documentation: str = "https://docs.langflow.org/integrations/notion/search"
    icon = "NotionDirectoryLoader"

    field_order = [
        "notion_secret",
        "query",
        "filter_value",
        "sort_direction",
    ]

    def build_config(self):
        return {
            "notion_secret": {
                "display_name": "Notion Secret",
                "field_type": "str",
                "info": "The Notion integration token.",
                "password": True,
            },
            "query": {
                "display_name": "Search Query",
                "field_type": "str",
                "info": "The text that the API compares page and database titles against.",
            },
            "filter_value": {
                "display_name": "Filter Type",
                "field_type": "str",
                "info": "Limits the results to either only pages or only databases.",
                "options": ["page", "database"],
                "default_value": "page",
            },
            "sort_direction": {
                "display_name": "Sort Direction",
                "field_type": "str",
                "info": "The direction to sort the results.",
                "options": ["ascending", "descending"],
                "default_value": "descending",
            },
        }

    def build(
        self,
        notion_secret: str,
        query: str = "",
        filter_value: str = "page",
        sort_direction: str = "descending",
    ) -> List[Record]:
        try:
            url = "https://api.notion.com/v1/search"
            headers = {
                "Authorization": f"Bearer {notion_secret}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            }

            data = {
                "query": query,
                "filter": {
                    "value": filter_value,
                    "property": "object"
                },
                "sort":{
                  "direction": sort_direction,
                  "timestamp": "last_edited_time"
                }
            }

            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            results = response.json()
            records = []
            combined_text = f"Results found: {len(results['results'])}\n\n"
            for result in results['results']:
                result_data = {
                    'id': result['id'],
                    'type': result['object'],
                    'last_edited_time': result['last_edited_time'],
                }

                if result['object'] == 'page':
                    result_data['title_or_url'] = result['url']
                    text = f"id: {result['id']}\ntitle_or_url: {result['url']}\n"
                elif result['object'] == 'database':
                    if 'title' in result and isinstance(result['title'], list) and len(result['title']) > 0:
                        result_data['title_or_url'] = result['title'][0]['plain_text']
                        text = f"id: {result['id']}\ntitle_or_url: {result['title'][0]['plain_text']}\n"
                    else:
                        result_data['title_or_url'] = "N/A"
                        text = f"id: {result['id']}\ntitle_or_url: N/A\n"

                text += f"type: {result['object']}\nlast_edited_time: {result['last_edited_time']}\n\n"
                combined_text += text
                records.append(Record(text=text, data=result_data))

            self.status = combined_text
            return records

        except Exception as e:
            self.status = f"An error occurred: {str(e)}"
            return [Record(text=self.status, data=[])]
```

## Example Usage

<Admonition type="info" title="Example Usage">
Here's an example of how you can use the `NotionSearch` component in a Langflow flow:

<ZoomableImage
alt="NotionSearch Flow Example"
sources={{
    light: "img/notion/NotionSearch_flow_example.png",
    dark: "img/notion/NotionSearch_flow_example_dark.png",
    }}
style={{ width: "100%", margin: "20px 0" }}
/>

In this example, the `NotionSearch` component is used to search for pages and databases in Notion based on the provided query and filter criteria. The retrieved data can then be processed further in the subsequent components of the flow.
</Admonition>

## Best Practices

When using the `NotionSearch` component, consider these best practices:

- Ensure you have a valid Notion integration token with the necessary permissions to search for pages and databases.
- Provide a meaningful search query to narrow down the results to the desired pages or databases.
- Choose the appropriate filter type (`page` or `database`) based on your search requirements.
- Consider the sorting direction (`ascending` or `descending`) to organize the search results effectively.

The `NotionSearch` component provides a powerful way to integrate Notion search capabilities into your Langflow workflows. By leveraging this component, you can easily search for pages and databases in Notion based on custom queries and filters, enabling you to build more dynamic and data-driven flows.

We encourage you to explore the capabilities of the `NotionSearch` component further and experiment with different search scenarios to unlock the full potential of integrating Notion search into your Langflow workflows.

## Troubleshooting

If you encounter any issues while using the `NotionSearch` component, consider the following:

- Double-check that the `notion_secret` is correct and valid.
- Verify that the Notion integration has the necessary permissions to access the desired pages and databases.
- Check the Notion API documentation for any updates or changes that may affect the component's functionality.
