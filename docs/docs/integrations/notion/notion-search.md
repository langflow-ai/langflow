import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Notion Search

Langflow allows you to extend its functionality with custom components. The `NotionSearch` component is designed to search all pages and databases that have been shared with an integration in Notion. It provides a convenient way to integrate Notion search capabilities into your Langflow workflows.

> **Tip**:
>
> ### Component Functionality
>
> The `NotionSearch` component enables you to:
>
> - Search for pages and databases in Notion that have been shared with an integration
> - Filter the search results based on object type (pages or databases)
> - Sort the search results in ascending or descending order based on the last edited time

## Component Usage

To use the `NotionSearch` component in a Langflow flow, follow these steps:

1. **Add the `NotionSearch` component to your flow.**
2. **Configure the component by providing the required parameters:**
   - `notion_secret`: The Notion integration token for authentication.
   - `query`: The text to search for in page and database titles.
   - `filter_value`: The type of objects to include in the search results (pages or databases).
   - `sort_direction`: The direction to sort the search results (ascending or descending).
3. **Connect the `NotionSearch` component to other components in your flow as needed.**

### Example Component Code

```python
# Placeholder for the component code
```

## Example Usage

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

## Best Practices

> **Tip**:
>
> ### Best Practices
>
> When using the `NotionSearch` component, consider the following best practices:
>
> - Ensure that you have a valid Notion integration token with the necessary permissions to search for pages and databases.
> - Provide a meaningful search query to narrow down the results to the desired pages or databases.
> - Choose the appropriate filter type (`page` or `database`) based on your search requirements.
> - Consider the sorting direction (`ascending` or `descending`) to organize the search results effectively.

## Troubleshooting

> **Warning**:
>
> ### Troubleshooting
>
> If you encounter any issues while using the `NotionSearch` component, consider the following:
>
> - Double-check that the `notion_secret` is correct and valid.
> - Verify that the Notion integration has the necessary permissions to access the desired pages and databases.
> - Check the Notion API documentation for any updates or changes that may affect the component's functionality.

The `NotionSearch` component provides a powerful way to integrate Notion search capabilities into your Langflow workflows. By leveraging this component, you can easily search for pages and databases in Notion based on custom queries and filters, enabling you to build more dynamic and data-driven flows.

We encourage you to explore the capabilities of the `NotionSearch` component further and experiment with different search scenarios to unlock the full potential of integrating Notion search into your Langflow workflows.
