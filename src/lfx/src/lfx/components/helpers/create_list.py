from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import StrInput
from lfx.schema.data import JSON, Data
from lfx.schema.dataframe import DataFrame, Table
from lfx.template.field.base import Output


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
        Output(display_name="Table", name="dataframe", method="as_dataframe"),
    ]

    def create_list(self) -> list[JSON]:
        data = [Data(text=text) for text in self.texts]
        self.status = data
        return data

    def as_dataframe(self) -> Table:
        """Convert the list of Data objects into a DataFrame.

        Returns: Table: A DataFrame containing the list data.
        """
        return DataFrame(self.create_list())
