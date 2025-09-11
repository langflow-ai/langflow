from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import StrInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.template.field.base import Output


class CreateListComponent(Component):
    display_name = "Create List"
    description = "Creates a list of texts."
    icon = "list"
    name = "CreateList"
    legacy = True

    inputs = [
        StrInput(
            name="texts",
            display_name="Texts",
            info="Enter one or more texts.",
            is_list=True,
        ),
    ]

    outputs = [
        Output(display_name="Data List", name="list", method="create_list"),
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    def create_list(self) -> list[Data]:
        data = [Data(text=text) for text in self.texts]
        self.status = data
        return data

    def as_dataframe(self) -> DataFrame:
        """Convert the list of Data objects into a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the list data.
        """
        return DataFrame(self.create_list())
