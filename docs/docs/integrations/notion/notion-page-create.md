import Admonition from "@theme/Admonition";

# NotionPageCreator Component in Langflow

Langflow allows you to extend its functionality with custom components. The `NotionPageCreator` component is designed to create pages in a Notion database. It provides a convenient way to integrate Notion page creation into your Langflow workflows.

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

Here's the code block for the `NotionPageCreator` component:

```python
class NotionPageCreator(CustomComponent):
    display_name = "Create Page [Notion]"
    description = "A component for creating Notion pages."
    documentation: str = "https://developers.notion.com/reference/post-database-query"
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
    ) -> Record:
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
            response = response.json()
            page_id = response["id"]
            page_url = response["url"]
            return_message = f"Successfully created Notion page with ID: {page_id}\n Page URL: {page_url}"
            self.status=return_message
            
            return Record(text=return_message, page_id=page_id, url=page_url)
        else:
            error_message = f"Failed to create Notion page. Status code: {response.status_code}, Error: {response.text}"
            self.status = error_message
            raise Exception(error_message)
        return Record(text="Not able to connect to notion")
```

<Admonition type="info" title="Example Usage">
Here's an example of how to use the `NotionPageCreator` component in a Langflow flow:

<ZoomableImage
  alt="NotionPageCreator Flow Example"
  sources={{
    light: "img/NotionPageCreator_flow_example.png",
    dark: "img/NotionPageCreator_flow_example.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>
</Admonition>

## Best Practices

<Admonition type="tip" title="Best Practices">
When using the `NotionPageCreator` component, consider the following best practices:
- Ensure that you have a valid Notion integration token with the necessary permissions to create pages in the specified database.
- Properly format the `properties` input as a JSON string, matching the structure and field types of your Notion database.
- Handle any errors or exceptions that may occur during the page creation process and provide appropriate error messages.
</Admonition>

## Troubleshooting

<Admonition type="warning" title="Troubleshooting">
If you encounter any issues while using the `NotionPageCreator` component, consider the following:
- Double-check that the `database_id` and `notion_secret` inputs are correct and valid.
- Verify that the `properties` input is properly formatted as a JSON string and matches the structure of your Notion database.
- Check the Notion API documentation for any updates or changes that may affect the component's functionality.
</Admonition>

The `NotionPageCreator` component simplifies the process of creating pages in a Notion database directly from your Langflow workflows. By leveraging this component, you can seamlessly integrate Notion page creation functionality into your automated processes, saving time and effort. Feel free to explore the capabilities of the `NotionPageCreator` component and adapt it to suit your specific requirements.
