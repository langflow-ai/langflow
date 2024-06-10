import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# User List

The `NotionUserList` component retrieves users from Notion. It provides a convenient way to integrate Notion user data into your Langflow workflows.

[Notion Reference](https://developers.notion.com/reference/get-users)

The `NotionUserList` component enables you to:

- Retrieve user data from Notion
- Access user information such as ID, type, name, and avatar URL
- Integrate Notion user data seamlessly into your Langflow workflows

## Component Usage

To use the `NotionUserList` component in a Langflow flow, follow these steps:

1. Add the `NotionUserList` component to your flow.
2. Configure the component by providing the required Notion secret token.
3. Connect the component to other nodes in your flow as needed.

## Component Python code

```python
import requests
from typing import List

from langflow import CustomComponent
from langflow.schema import Record


class NotionUserList(CustomComponent):
    display_name = "List Users [Notion]"
    description = "Retrieve users from Notion."
    documentation: str = "https://docs.langflow.org/integrations/notion/list-users"
    icon = "NotionDirectoryLoader"

    def build_config(self):
        return {
            "notion_secret": {
                "display_name": "Notion Secret",
                "field_type": "str",
                "info": "The Notion integration token.",
                "password": True,
            },
        }

    def build(
        self,
        notion_secret: str,
    ) -> List[Record]:
        url = "https://api.notion.com/v1/users"
        headers = {
            "Authorization": f"Bearer {notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        results = data['results']

        records = []
        for user in results:
            id = user['id']
            type = user['type']
            name = user.get('name', '')
            avatar_url = user.get('avatar_url', '')

            record_data = {
                "id": id,
                "type": type,
                "name": name,
                "avatar_url": avatar_url,
            }

            output = "User:\n"
            for key, value in record_data.items():
                output += f"{key.replace('_', ' ').title()}: {value}\n"
            output += "________________________\n"

            record = Record(text=output, data=record_data)
            records.append(record)

        self.status = "\n".join(record.text for record in records)
        return records
```

## Example Usage

Here's an example of how you can use the `NotionUserList` component in a Langflow flow and passing the outputs to the Prompt component:

<ZoomableImage
alt="NotionUserList Flow Example"
sources={{
      light: "img/notion/NotionUserList_flow_example.png",
      dark: "img/notion/NotionUserList_flow_example_dark.png",
  }}
style={{ width: "100%", margin: "20px 0" }}
/>

## Best Practices

When using the `NotionUserList` component, consider the following best practices:

- Ensure that you have a valid Notion integration token with the necessary permissions to retrieve user data.
- Handle the retrieved user data securely and in compliance with Notion's API usage guidelines.

The `NotionUserList` component provides a seamless way to integrate Notion user data into your Langflow workflows. By leveraging this component, you can easily retrieve and utilize user information from Notion, enhancing the capabilities of your Langflow applications. Feel free to explore and experiment with the `NotionUserList` component to unlock new possibilities in your Langflow projects!

## Troubleshooting

If you encounter any issues while using the `NotionUserList` component, consider the following:

- Double-check that your Notion integration token is valid and has the required permissions.
- Verify that you have installed the necessary dependencies (`requests`) for the component to function properly.
- Check the Notion API documentation for any updates or changes that may affect the component's functionality.
