from loguru import logger

from langflow.custom import Component
from langflow.helpers.data import data_to_text_list
from langflow.io import DataInput, Output
from langflow.schema import Data


class LabValuesExtraction(Component):
    display_name = "Lab Values Extraction"
    description = "Identifies and extracts relevant lab results from medical records."
    icon = "Autonomize"
    name = "LabValuesExtraction"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The data to convert to text.",
            is_list=True,
        ),
        # MultilineInput(
        #     name="template",
        #     display_name="Template",
        #     info="The template to use for formatting the data. "
        #     "It can contain the keys {text}, {data} or any other key in the Data.",
        #     value="{text}",
        # ),
        # StrInput(name="sep", display_name="Separator", advanced=True, value="\n"),
    ]

    outputs = [
        # Output(
        #     display_name="Text",
        #     name="text",
        #     info="Data as a single Message, with each input Data separated by Separator",
        #     method="parse_data",
        # ),
        Output(
            display_name="Data List",
            name="data_list",
            info="Data as a list of new Data, each having `text` formatted by Template",
            method="parse_data_as_list",
        ),
    ]

    def _clean_args(self) -> tuple[list[Data], str, str]:
        data = self.data if isinstance(self.data, list) else [self.data]
        return data

    def parse_data_as_list(self) -> Data:
        data = self._clean_args()
        text_list, data_list = data_to_text_list("{value}", data)
        for item, text in zip(data_list, text_list, strict=True):
            item.set_text(text)
        extracted_values = self.extract_lab_values(data_list)
        result = Data(value={"data": extracted_values})
        return result

    def extract_lab_values(self, data) -> list[Data]:
        logger.info(f"lab values {data}")
        lab_values = []
        for item in data:
            for prediction in item.data["value"]["data"]["prediction"]:
                category = prediction["Category"]
                logger.info(f"category--- {category}")
                if category in ["TEST_TREATMENT_PROCEDURE"]:
                    lab_values.append(prediction)
        return lab_values
