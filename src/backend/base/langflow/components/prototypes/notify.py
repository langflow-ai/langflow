from langflow.custom import Component
from langflow.io import BoolInput, DataInput, MessageTextInput, Output
from langflow.schema import Data


class NotifyComponent(Component):
    """Generates a notification to the 'Listen' component."""

    display_name = "Notify"
    description = "Generates a notification to the 'Listen' component."
    name = "Notify"
    beta: bool = True

    inputs = [
        MessageTextInput(name="name_of_state", display_name="Name", info="The identifier for the notification state."),
        DataInput(name="data", display_name="Data", info="The data content to store in the notification."),
        BoolInput(name="append", display_name="Append", info="If True, appends the data to the existing notification."),
    ]

    outputs = [Output(name="output_data", display_name="Data", method="build_notify")]

    def build_notify(self) -> Data:
        """Builds the notification data and updates the component's state."""
        try:
            name_of_state = getattr(self, "name_of_state", None)
            if not name_of_state:
                self.status = "Error: 'Name' is required."
                error_message = "The 'Name' input cannot be empty"
                raise ValueError(error_message)

            data_input = getattr(self, "data", None)
            if data_input and not isinstance(data_input, Data):
                # Using | operator for type checks (Python 3.10+)
                data = data_input if isinstance(data_input, str | dict) else data_input
            elif not data_input:
                data = Data(text="")
            else:
                data = data_input

            # Determine 'append' behavior
            append = getattr(self, "append", False)
            if append:
                self.append_state(name_of_state, data)
            else:
                self.update_state(name_of_state, data)

            self._set_successors_ids()
        except Exception as exc:
            error_msg = f"Error in build_notify: {exc!s}"
            self.status = error_msg
            raise
        else:
            return data

    def _set_successors_ids(self):
        """Sets the successor IDs for the vertex."""
        try:
            self._vertex.is_state = True
            successors = self._vertex.graph.successor_map.get(self._vertex.id, [])
            return successors + self._vertex.graph.activated_vertices
        except Exception as exc:
            error_msg = f"Error in _set_successors_ids: {exc!s}"
            self.status = error_msg
            raise
