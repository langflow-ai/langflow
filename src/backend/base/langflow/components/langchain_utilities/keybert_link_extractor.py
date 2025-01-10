from typing import Any

from langchain_community.graph_vectorstores.extractors import KeybertLinkExtractor
from langchain_community.graph_vectorstores.links import add_links
from langchain_core.documents import Document
from loguru import logger

from langflow.base.document_transformers.model import Component
from langflow.inputs import BoolInput, DataInput, StrInput
from langflow.io import Output
from langflow.schema import Data


class KeybertLinkExtractorComponent(Component):
    display_name = "Keybert Link Extractor"
    description = "Extract keywords using keybert."
    documentation = "https://python.langchain.com/v0.2/api_reference/community/graph_vectorstores/langchain_community.graph_vectorstores.extractors.html_link_extractor.KeybertExtractor.html"
    name = "KeybertExtractor"
    icon = "LangChain"

    inputs = [
        DataInput(
            name="data_input",
            display_name="Input",
            info="The texts from which to extract links.",
            input_types=["Document", "Data"],
        ),
        StrInput(
            name="sep",
            display_name="Separator",
            info="Character for splitting the text into paragraphs.",
            value="\n\n",
            refresh_button=True,
            required=True,
        ),
        BoolInput(
            name="split",
            display_name="Split",
            value=True,
            required=False,
            info="Split the text into sentences before extracting links.",
        ),
    ]

    outputs = [
        Output(
            name="data_output",
            display_name="Data",
            info="List of Input objects each with added Metadata",
            method="process_output",
        ),
    ]

    def get_data_input(self) -> Any:
        return self.data_input

    def process_output(self) -> list[Data]:
        """Processes the input data to extract links using the KeybertLinkExtractor.

        Returns:
            list[Data]: A list of Data objects with extracted links added as metadata.

        Raises:
            AttributeError: If the input data does not have a 'text' attribute.
        """
        data_input = self.get_data_input()

        # Always expect a list of Data objects
        if not isinstance(data_input, list):
            data_input = [data_input]

        logger.debug("Building Keybert Link Extractor")

        # Keybert extractor us BERT-embeddings to extract keywords
        extractor = KeybertLinkExtractor()

        # For each inout text, extract links
        documents = []
        for data in data_input:
            # How to I ensure that .text always exists?
            data = data.text

            chuncks = []

            if self.split:
                chuncks = data.split(self.sep)
            else:
                chuncks = [data]

            for chunk in chuncks:
                document = Document(chunk)
                links = extractor.extract_one(chunk)
                add_links(document, links)
                documents.append(document)

            logger.debug(documents)

        return documents
