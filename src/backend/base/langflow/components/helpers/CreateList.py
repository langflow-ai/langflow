from langflow.custom import Component
from langflow.inputs import StrInput
from langflow.schema import Data
from langflow.template import Output


class CreateListComponent(Component):
    display_name = "Create List"
    description = "Creates a list of texts."
    icon = "list"
    name = "CreateList"

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
    ]

    def create_list(self) -> list[Data]:
        data = [Data(text=text) for text in self.texts]
        self.status = data
        return data
