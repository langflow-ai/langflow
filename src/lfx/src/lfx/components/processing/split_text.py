from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, Output, TabInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.utils.util import unescape_string


class SplitTextComponent(Component):
    display_name: str = "Split Text"
    description: str = "Split text into chunks based on specified criteria."
    documentation: str = "https://docs.langflow.org/split-text"
    icon = "scissors-line-dashed"
    name = "SplitText"

    inputs = [
        HandleInput(
            name="data_inputs",
            display_name="Input",
            info="The data with texts to split in chunks.",
            input_types=["Data", "DataFrame", "Message"],
            required=True,
        ),
        TabInput(
            name="mode",
            display_name="Mode",
            options=["Recursive", "Character"],
            value="Recursive",
            info=(
                "Character: splits by a single separator, configurable. "
                "Recursive: tries multiple separators in cascade to guarantee chunk size."
            ),
            real_time_refresh=True,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="The maximum number of characters in each chunk.",
            value=1000,
        ),
        IntInput(
            name="chunk_overlap",
            display_name="Chunk Overlap",
            info="Number of characters to overlap between consecutive chunks.",
            value=200,
        ),
        DropdownInput(
            name="separator",
            display_name="Separator",
            info="The character to split on.",
            options=["/n/n", "/n", ".", ",", '" "', '""', "Custom"],
            value="/n/n",
            show=False,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="custom_separator",
            display_name="Custom Separator",
            info="Enter a custom separator. Use \\n for newline, \\t for tab.",
            value="",
            show=False,
        ),
        MessageTextInput(
            name="text_key",
            display_name="Text Key",
            info="The key to use for the text column.",
            value="text",
            advanced=True,
        ),
        DropdownInput(
            name="keep_separator",
            display_name="Keep Separator",
            info="Whether to keep the separator in the output chunks and where to place it.",
            options=["False", "True", "Start", "End"],
            value="False",
            advanced=True,
        ),
        BoolInput(
            name="clean_output",
            display_name="Clean Output",
            info="When enabled, only the text column is included in the output. Metadata columns are removed.",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Chunks", name="dataframe", method="split_text"),
    ]

    def update_build_config(self, build_config, field_value, field_name=None):
        if field_name == "mode":
            is_character_mode = field_value == "Character"
            build_config["separator"]["show"] = is_character_mode
            build_config["custom_separator"]["show"] = (
                is_character_mode and build_config["separator"]["value"] == "Custom"
            )
        if field_name == "separator":
            build_config["custom_separator"]["show"] = field_value == "Custom"
        return build_config

    def _docs_to_data(self, docs, *, clean: bool = False) -> list[Data]:
        return [
            Data(text=doc.page_content) if clean else Data(text=doc.page_content, data=doc.metadata) for doc in docs
        ]

    def _fix_separator(self, separator: str) -> str:
        if separator == "/n/n":
            return "\n\n"
        if separator == "/n":
            return "\n"
        if separator == "/t":
            return "\t"
        if separator == '" "':
            return " "
        if separator == '""':
            return ""
        return separator

    def _parse_keep_separator(self, value: str) -> bool | str:
        if value.lower() == "false":
            return False
        if value.lower() == "true":
            return True
        return value  # 'start' or 'end' kept as string

    def _get_documents(self):
        inputs = self.data_inputs

        if isinstance(inputs, DataFrame):
            if not len(inputs):
                msg = "DataFrame is empty"
                raise TypeError(msg)
            inputs.text_key = self.text_key
            try:
                return inputs.to_lc_documents()
            except Exception as e:
                msg = f"Error converting DataFrame to documents: {e}"
                raise TypeError(msg) from e

        if isinstance(inputs, Message):
            inputs = [inputs.to_data()]
        elif isinstance(inputs, Data):
            inputs = [inputs]

        if not inputs:
            msg = "No data inputs provided"
            raise TypeError(msg)

        try:
            documents = []
            for item in inputs:
                if isinstance(item, Data):
                    item.text_key = self.text_key
                    documents.append(item.to_lc_document())
        except AttributeError as e:
            msg = f"Invalid input type in collection: {e}"
            raise TypeError(msg) from e

        if not documents:
            msg = f"No valid Data inputs found in {type(inputs)}"
            raise TypeError(msg)

        return documents

    def _split_by_character(self, documents):
        if self.separator == "Custom":
            separator = unescape_string(self.custom_separator)
        else:
            separator = unescape_string(self._fix_separator(self.separator))
        keep_sep = self._parse_keep_separator(self.keep_separator)
        splitter = CharacterTextSplitter(
            separator=separator,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            keep_separator=keep_sep,
            length_function=len,
        )
        return splitter.split_documents(documents)

    def _split_by_recursive(self, documents):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        return splitter.split_documents(documents)

    def split_text_base(self):
        try:
            documents = self._get_documents()
            if self.mode == "Recursive":
                return self._split_by_recursive(documents)
            return self._split_by_character(documents)
        except TypeError:
            raise
        except Exception as e:
            msg = f"Error splitting text: {e}"
            raise TypeError(msg) from e

    def split_text(self) -> DataFrame:
        docs = self.split_text_base()
        df = DataFrame(self._docs_to_data(docs, clean=self.clean_output))
        return df if self.clean_output else df.smart_column_order()
