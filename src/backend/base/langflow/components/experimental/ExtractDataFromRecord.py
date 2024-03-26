from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record


class ExtractKeyFromRecordComponent(CustomComponent):
    display_name = "Extract Key From Record"
    description = "Extracts a key from a record."
    beta: bool = True

    field_config = {
        "record": {"display_name": "Record"},
        "keys": {
            "display_name": "Keys",
            "info": "The keys to extract from the record.",
            "input_types": [],
        },
        "silent_error": {
            "display_name": "Silent Errors",
            "info": "If True, errors will not be raised.",
            "advanced": True,
        },
    }

    def build(self, record: Record, keys: list[str], silent_error: bool = True) -> Record:
        """
        Extracts the keys from a record.

        Args:
            record (Record): The record from which to extract the keys.
            keys (list[str]): The keys to extract from the record.
            silent_error (bool): If True, errors will not be raised.

        Returns:
            dict: The extracted keys.
        """
        extracted_keys = {}
        for key in keys:
            try:
                extracted_keys[key] = getattr(record, key)
            except AttributeError:
                if not silent_error:
                    raise KeyError(f"The key '{key}' does not exist in the record.")
        return_record = Record(data=extracted_keys)
        self.status = return_record
        return return_record
