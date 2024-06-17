from typing import List

from langflow.custom import Component
from langflow.inputs import HandleInput, IntInput, TextInput
from langflow.schema import Data
from langflow.template import Output
from langflow.utils.util import unescape_string


class SplitContentComponent(Component):
    display_name: str = "Split Content"
    description: str = "Split textual content into chunks based on specified criteria."
    icon = "split"

    inputs = [
        HandleInput(name="data", display_name="Data", info="Data with text to split.", input_types=["Data"]),
        TextInput(
            name="content_key",
            display_name="Content Key",
            info="The key to access the text content in the Data object.",
            value="content",
        ),
        TextInput(
            name="separator",
            display_name="Separator",
            info='The character to split on. Defaults to "\n".',
            value="\n",
            advanced=True,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="The target length (in number of characters) of each chunk.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="min_chunk_size",
            display_name="Minimum Chunk Size",
            info="The minimum size of chunks. Smaller chunks will be merged.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="max_chunk_size",
            display_name="Maximum Chunk Size",
            info="The maximum size of chunks. Larger chunks will be split.",
            value=0,
            advanced=True,
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
        min_chunk_size = self.min_chunk_size
        max_chunk_size = self.max_chunk_size
        results = []
        buffer = ""

        for row in data:
            content = row.data.get(content_key, "")
            if chunk_size > 0:
                chunks = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]
            else:
                chunks = content.split(separator)

            for chunk in chunks:
                buffer += chunk
                while len(buffer) >= max_chunk_size:
                    results.append(Data(data={"parent": content, "chunk": buffer[:max_chunk_size]}))
                    buffer = buffer[max_chunk_size:]
                if len(buffer) >= min_chunk_size:
                    results.append(Data(data={"parent": content, "chunk": buffer}))
                    buffer = ""

        # Handle any remaining content that may not meet the min_chunk_size requirement
        if buffer:
            results.append(Data(data={"parent": content, "chunk": buffer}))

        self.status = results
        return results
