from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data


class ListenComponent(Component):
    """A component to listen for a notification."""

    display_name = "Listen"
    description = "Listens for a notification and retrieves its data."
    name = "Listen"
    beta: bool = True

    inputs = [
        MessageTextInput(
            name="name_of_state", display_name="Name", info="The identifier of the notification to listen for."
        )
    ]

    outputs = [Output(name="output_data", display_name="Data", method="build_listen")]

    def build_listen(self) -> Data:
        """Retrieves the notification data based on the given name."""
        state = None
        try:
            name_of_state = getattr(self, "name_of_state", None)
            if not name_of_state:
                self.status = "Error: 'Name' is required."
                error_msg = "The 'Name' input cannot be empty."
                raise ValueError(error_msg)

            # Retrieve the state
            state = self.get_state(name_of_state)
            if state is None:
                self.status = f"No notification found for '{name_of_state}'"
                lookup_error_msg = f"No state found for '{name_of_state}'"
                raise LookupError(lookup_error_msg)
        except Exception as e:
            self.status = f"Error in build_listen: {e!s}"
            raise
        else:
            self._set_successors_ids()
            return state

    def _set_successors_ids(self):
        """Sets the successor IDs for the vertex."""
        try:
            self._vertex.is_state = True
            successors = self._vertex.graph.successor_map.get(self._vertex.id, [])
            return successors + self._vertex.graph.activated_vertices
        except Exception as e:
            self.status = f"Error in _set_successors_ids: {e!s}"
            raise
