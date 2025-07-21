"""Enhanced Data class for langflow that inherits from lfx base and adds complex methods."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from lfx.schema.data import Data as BaseData

from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER
from langflow.utils.image import create_image_content_dict

if TYPE_CHECKING:
    from langflow.schema.dataframe import DataFrame
    from langflow.schema.message import Message


class Data(BaseData):
    """Enhanced Data class with langflow-specific methods.

    This class inherits from lfx.schema.data.Data and adds methods that require
    langflow-specific dependencies like services, templates, and other schema modules.
    """

    def to_lc_message(self) -> BaseMessage:
        """Converts the Data to a BaseMessage (full version with file support).

        Returns:
            BaseMessage: The converted BaseMessage.
        """
        # The idea of this function is to be a helper to convert a Data to a BaseMessage
        # It will use the "sender" key to determine if the message is Human or AI
        # If the key is not present, it will default to AI
        # But first we check if all required keys are present in the data dictionary
        # they are: "text", "sender"
        if not all(key in self.data for key in ["text", "sender"]):
            msg = f"Missing required keys ('text', 'sender') in Data: {self.data}"
            raise ValueError(msg)
        sender = self.data.get("sender", MESSAGE_SENDER_AI)
        text = self.data.get("text", "")
        files = self.data.get("files", [])
        if sender == MESSAGE_SENDER_USER:
            if files:
                from langflow.schema.image import get_file_paths

                resolved_file_paths = get_file_paths(files)
                contents = [create_image_content_dict(file_path) for file_path in resolved_file_paths]
                # add to the beginning of the list
                contents.insert(0, {"type": "text", "text": text})
                human_message = HumanMessage(content=contents)
            else:
                human_message = HumanMessage(
                    content=[{"type": "text", "text": text}],
                )

            return human_message

        return AIMessage(content=text)

    def filter_data(self, filter_str: str) -> Data:
        """Filters the data dictionary based on the filter string.

        Args:
            filter_str (str): The filter string to apply to the data dictionary.

        Returns:
            Data: The filtered Data.
        """
        from langflow.template.utils import apply_json_filter

        return apply_json_filter(self.data, filter_str)

    def to_message(self) -> Message:
        """Converts the Data to a Message.

        Returns:
            Message: The converted Message.
        """
        from langflow.schema.message import Message  # Local import to avoid circular import

        if self.text_key in self.data:
            return Message(text=self.get_text())
        return Message(text=str(self.data))

    def to_dataframe(self) -> DataFrame:
        """Converts the Data to a DataFrame.

        Returns:
            DataFrame: The converted DataFrame.
        """
        from langflow.schema.dataframe import DataFrame  # Local import to avoid circular import

        data_dict = self.data
        # If data contains only one key and the value is a list of dictionaries, convert to DataFrame
        if (
            len(data_dict) == 1
            and isinstance(next(iter(data_dict.values())), list)
            and all(isinstance(item, dict) for item in next(iter(data_dict.values())))
        ):
            return DataFrame(data=next(iter(data_dict.values())))
        return DataFrame(data=[self])

    def __deepcopy__(self, memo):
        """Custom deepcopy implementation to handle copying of the Data object."""
        import copy
        # Create a new Data object with a deep copy of the data dictionary
        # Use the same class (could be subclassed)
        return self.__class__(data=copy.deepcopy(self.data, memo), text_key=self.text_key, default_value=self.default_value)
