from typing import List
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langflow.schema.schema import Record


def records_to_messages(records: List[Record]) -> List[BaseMessage]:
    """
    Convert a list of records to a list of messages.

    Args:
        records (List[Record]): The records to convert.

    Returns:
        List[Message]: The records as messages.
    """
    return [record.to_lc_message() for record in records]
