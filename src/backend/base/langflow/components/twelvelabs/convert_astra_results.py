from typing import Any

from langflow.custom import Component
from langflow.io import HandleInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class ConvertAstraToTwelveLabs(Component):
    """Convert AstraDB search results to TwelveLabs Pegasus inputs."""

    display_name = "Convert AstraDB to Pegasus Input"
    description = "Converts AstraDB search results to inputs compatible with TwelveLabs Pegasus."
    icon = "TwelveLabs"
    name = "ConvertAstraToTwelveLabs"
    documentation = "https://github.com/twelvelabs-io/twelvelabs-developer-experience/blob/main/integrations/Langflow/TWELVE_LABS_COMPONENTS_README.md"

    inputs = [
        HandleInput(
            name="astra_results",
            display_name="AstraDB Results",
            input_types=["Data"],
            info="Search results from AstraDB component",
            required=True,
            is_list=True,
        )
    ]

    outputs = [
        Output(
            name="index_id",
            display_name="Index ID",
            type_=Message,
            method="get_index_id",
        ),
        Output(
            name="video_id",
            display_name="Video ID",
            type_=Message,
            method="get_video_id",
        ),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._video_id = None
        self._index_id = None

    def build(self, **kwargs: Any) -> None:  # noqa: ARG002 - Required for parent class compatibility
        """Process the AstraDB results and extract TwelveLabs index information."""
        if not self.astra_results:
            return

        # Convert to list if single item
        results = self.astra_results if isinstance(self.astra_results, list) else [self.astra_results]

        # Try to extract index information from metadata
        for doc in results:
            if not isinstance(doc, Data):
                continue

            # Get the metadata, handling the nested structure
            metadata = {}
            if hasattr(doc, "metadata") and isinstance(doc.metadata, dict):
                # Handle nested metadata using .get() method
                metadata = doc.metadata.get("metadata", doc.metadata)

            # Extract index_id and video_id
            self._index_id = metadata.get("index_id")
            self._video_id = metadata.get("video_id")

            # If we found both, we can stop searching
            if self._index_id and self._video_id:
                break

    def get_video_id(self) -> Message:
        """Return the extracted video ID as a Message."""
        self.build()
        return Message(text=self._video_id if self._video_id else "")

    def get_index_id(self) -> Message:
        """Return the extracted index ID as a Message."""
        self.build()
        return Message(text=self._index_id if self._index_id else "")
