import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# AddContentToPage Component in Langflow

Langflow allows extending its functionality with custom components like `AddContentToPage`, which converts markdown text to Notion blocks and appends them to a Notion page.

## Component Functionality

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

## Code Block for the `AddContentToPage` Component

```python
import json
from typing import List, Dict, Any
from markdown import markdown
from bs4 import BeautifulSoup
import requests

from langflow import CustomComponent
from langflow.schema import Record

class AddContentToPage(CustomComponent):
    display_name = "Add Content to Page [Notion]"
    description = "Convert markdown text to Notion blocks and append them to a Notion page."
    documentation: str = "https://developers.notion.com/reference/patch-block-children"
    icon = "NotionDirectoryLoader"

    def build_config(self):
        return {
            "markdown_text": {
                "display_name": "Markdown Text",
                "field_type": "str",
                "info": "The markdown text to convert to Notion blocks.",
                "multiline": True,
            },
             "block_id": {
                "display_name": "Page/Block ID",
                "field_type": "str",
                "info": "The ID of the page/block to add the content.",
            },
            "notion_secret": {
                "display_name": "Notion Secret",
                "field_type": "str",
                "info": "The Notion integration token.",
                "password": True,
            },
        }

    def build(self, markdown_text: str, block_id: str, notion_secret: str) -> Record:
        html_text = markdown(markdown_text)
        soup = BeautifulSoup(html_text, 'html.parser')
        blocks = self.process_node(soup)

        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        headers = {
            "Authorization": f"Bearer {notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        data = {
            "children": blocks,
        }

        response = requests.patch(url, headers=headers, json=data)
        self.status = str(response.json())
        response.raise_for_status()

        result = response.json()
        self.status = f"Appended {len(blocks)} blocks to page with ID: {block_id}"
        return Record(data=result, text=json.dumps(result))

    def process_node(self, node):
        blocks = []
        if isinstance(node, str):
            text = node.strip()
            if text:
                if text.startswith('#'):
                    heading_level = text.count('#', 0, 6)
                    heading_text = text[heading_level:].strip()
                    if heading_level == 1:
                        blocks.append(self.create_block('heading_1', heading_text))
                    elif heading_level == 2:
                        blocks.append(self.create_block('heading_2', heading_text))
                    elif heading_level == 3:
                        blocks.append(self.create_block('heading_3', heading_text))
                else:
                    blocks.append(self.create_block('paragraph', text))
        elif node.name == 'h1':
            blocks.append(self.create_block('heading_1', node.get_text(strip=True)))
        elif node.name == 'h2':
            blocks.append(self.create_block('heading_2', node.get_text(strip=True)))
        elif node.name == 'h3':
            blocks.append(self.create_block('heading_3', node.get_text(strip=True)))
        elif node.name == 'p':
            code_node = node.find('code')
            if code_node:
                code_text = code_node.get_text()
                language, code = self.extract_language_and_code(code_text)
                blocks.append(self.create_block('code', code, language=language))
            elif self.is_table(str(node)):
                blocks.extend(self.process_table(node))
            else:
                blocks.append(self.create_block('paragraph', node.get_text(strip=True)))
        elif node.name == 'ul':
            blocks.extend(self.process_list(node, 'bulleted_list_item'))
        elif node.name == 'ol':
            blocks.extend(self.process_list(node, 'numbered_list_item'))
        elif node.name == 'blockquote':
            blocks.append(self.create_block('quote', node.get_text(strip=True)))
        elif node.name == 'hr':
            blocks.append(self.create_block('divider', ''))
        elif node.name == 'img':
            blocks.append(self.create_block('image', '', image_url=node.get('src')))
        elif node.name == 'a':
            blocks.append(self.create_block('bookmark', node.get_text(strip=True), link_url=node.get('href')))
        elif node.name == 'table':
            blocks.extend(self.process_table(node))

        for child in node.children:
            if isinstance(child, str):
                continue
            blocks.extend(self.process_node(child))

        return blocks

    def extract_language_and_code(self, code_text):
        lines = code_text.split('\n')
        language = lines[0].strip()
        code = '\n'.join(lines[1:]).strip()
        return language, code

    def is_code_block(self, text):
        return text.startswith('```')

    def extract_code_block(self, text):
        lines = text.split('\n')
        language = lines[0].strip('`').strip()
        code = '\n'.join(lines[1:]).strip('`').strip()
        return language, code
    
    def is_table(self, text):
        rows = text.split('\n')
        if len(rows) < 2:
            return False

        has_separator = False
        for i, row in enumerate(rows):
            if '|' in row:
                cells = [cell.strip() for cell in row.split('|')]
                cells = [cell for cell in cells if cell]  # Remove empty cells
                if i == 1 and all(set(cell) <= set('-|') for cell in cells):
                    has_separator = True
                elif not cells:
                    return False

        return has_separator and len(rows) >= 3

    def process_list(self, node, list_type):
        blocks = []
        for item in node.find_all('li'):
            item_text = item.get_text(strip=True)
            checked = item_text.startswith('[x]')
            is_checklist = item_text.startswith('[ ]') or checked

            if is_checklist:
                item_text = item_text.replace('[x]', '').replace('[ ]', '').strip()
                blocks.append(self.create_block('to_do', item_text, checked=checked))
            else:
                blocks.append(self.create_block(list_type, item_text))
        return blocks

    def process_table(self, node):
        blocks = []
        header_row = node.find('thead').find('tr') if node.find('thead') else None
        body_rows = node.find('tbody').find_all('tr') if node.find('tbody') else []

        if header_row or body_rows:
            table_width = max(len(header_row.find_all(['th', 'td'])) if header_row else 0,
                            max(len(row.find_all(['th', 'td'])) for row in body_rows))

            table_block = self.create_block('table', '', table_width=table_width, has_column_header=bool(header_row))
            blocks.append(table_block)

            if header_row:
                header_cells = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
                header_row_block = self.create_block('table_row', header_cells)
                blocks.append(header_row_block)

            for row in body_rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
                row_block = self.create_block('table_row', cells)
                blocks.append(row_block)

        return blocks
    
    def create_block(self, block_type: str, content: str, **kwargs) -> Dict[str, Any]:
        block = {
            "object": "block",
            "type": block_type,
            block_type: {},
        }

        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "quote"]:
            block[block_type]["rich_text"] = [
                {
                    "type": "text",
                    "text": {
                        "content": content,
                    },
                }
            ]
        elif block_type == 'to_do':
            block[block_type]["rich_text"] = [
                {
                    "type": "text",
                    "text": {
                        "content": content,
                    },
                }
            ]
            block[block_type]['checked'] = kwargs.get('checked', False)
        elif block_type == 'code':
            block[block_type]['rich_text'] = [
                {
                    "type": "text",
                    "text": {
                        "content": content,
                    },
                }
            ]
            block[block_type]['language'] = kwargs.get('language', 'plain text')
        elif block_type == 'image':
            block[block_type] = {
                "type": "external",
                "external": {
                    "url": kwargs.get('image_url', '')
                }
            }
        elif block_type == 'divider':
            pass
        elif block_type == 'bookmark':
            block[block_type]['url'] = kwargs.get('link_url', '')
        elif block_type == 'table':
            block[block_type]['table_width'] = kwargs.get('table_width', 0)
            block[block_type]['has_column_header'] = kwargs.get('has_column_header', False)
            block[block_type]['has_row_header'] = kwargs.get('has_row_header', False)
        elif block_type == 'table_row':
            block[block_type]['cells'] = [[{'type': 'text', 'text': {'content': cell}} for cell in content]]

        return block
```

## Example Usage

Example of using the `AddContentToPage` component in a Langflow flow using a Markdown as input:

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

## Troubleshooting

If issues arise:

- Verify the Notion integration token’s validity and permissions.
- Check the Notion API documentation for updates.
- Ensure markdown text is properly formatted.
- Double-check the `block_id` for correctness.

The `AddContentToPage` component is a powerful tool for integrating Notion content creation into Langflow workflows, facilitating easy conversion of markdown text to Notion blocks and appending them to specific pages.
