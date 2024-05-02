from typing import Optional

from langflow.base.io.text import TextComponent
from langflow.field_typing import Text, Data


class CSVOutput(TextComponent):
    display_name = "CSV Output"
    description = "Used view csv files"

    field_config = {
        "input_value": {"display_name": "csv","info":"A csv blob","input_types":["Data"]},
        "separator": {"display_name": "separator","info":"The separator used in the csv file","input_types":["Text"], "field_type":"Text","default_value":";","options":[";", ",", "|"]},
    }

    def build(self, input_value: Data, separator) -> Data:
        return {"data": input_value, "separator": separator}
