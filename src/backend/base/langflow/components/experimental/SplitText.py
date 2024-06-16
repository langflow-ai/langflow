from typing import List

from langflow.custom import Component
from langflow.inputs import IntInput, StrInput, HandleInput
from langflow.schema import Data
from langflow.template import Output
from langflow.utils.util import unescape_string


class SplitContentComponent(Component):
    display_name: str = "Split Content"
    description: str = "Split textual content into chunks of a specified length."
    icon = "split"

    inputs = [
        HandleInput(
            name="data",
            display_name="Data",
            info="Data with text to split.",
            input_types=["Data"]
        ),
        StrInput(
            name="content_key",
            display_name="Content Key",
            info="The key to access the text content in the Data object.",
            value="content",
        ),
        StrInput(
            name="separator",
            display_name="Separator",
            info='The character to split on. Defaults to "\n".',
            value="\n",
            advanced=True
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="The maximum length (in number of characters) of each chunk. Defaults to 0 (no chunking).",
            value=0,
            advanced=True
        ),
    ]

    outputs = [
        Output(display_name="Chunks", name="chunks", method="split_text"),
    ]

    def split_text(self) -> List[Data]:
        data = self.data if isinstance(self.data, list) else [self.data]
        content_key = self.content_key
        separator = unescape_string(self.separator)
        chunk_size = self.chunk_size
        results = []

        for row in data:
            content = row.data.get(content_key, '')
            if chunk_size > 0:
                chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
            else:
                chunks = content.split(separator)

            for chunk in chunks:
                if chunk.strip():
                    results.append(Data(data={"parent": content, "text": chunk}))

        self.status = results
        return results
