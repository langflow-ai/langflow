from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from langflow.custom import Component
from langflow.inputs import BoolInput, DataInput
from langflow.io import Output

if TYPE_CHECKING:
    from langflow.schema.data import Data
    from langflow.services.triggers.base_trigger import BaseTrigger


class BaseTriggerComponent(Component):
    """Base class for all trigger components.

    Trigger components are used to create tasks based on external events.
    Each trigger component should subclass this and implement the required methods.
    """

    # Base inputs that all trigger components will have
    _base_inputs = [
        DataInput(
            name="mock_data",
            display_name="Mock Data",
            info=(
                "Mock trigger data for testing purposes. "
                "When provided, this data will be included in the trigger output."
            ),
            advanced=True,
            required=False,
        ),
        BoolInput(
            name="is_testing",
            display_name="Testing Mode",
            info="Enable testing mode. When enabled, the trigger will output the mock data.",
            advanced=True,
            value=False,
        ),
    ]

    # Default outputs for all trigger components
    outputs = [
        Output(
            display_name="Trigger Info",
            name="trigger_info",
            method="get_trigger_info",
        ),
        Output(
            display_name="Output Value",
            name="output_value",
            method="get_trigger_info",
        ),
    ]

    def _validate_outputs(self) -> None:
        """Validate that the component has the required outputs."""
        required_output_methods = ["get_trigger_info"]
        output_methods = [output.method for output in self.outputs]

        for method_name in required_output_methods:
            if method_name not in output_methods:
                msg = f"Output with method '{method_name}' must be defined."
                raise ValueError(msg)
            if not hasattr(self, method_name):
                msg = f"Method '{method_name}' must be defined."
                raise ValueError(msg)

    @abstractmethod
    def get_trigger_info(self) -> Data:
        """Return information about this trigger.

        This method should return a Data object with information about the trigger,
        including its type, configuration, and other relevant details.

        If mock_data is provided and is_testing is True, the trigger info will
        include the mock data.

        Returns:
            Data: A Data object containing trigger information
        """

    @abstractmethod
    def get_trigger_instance(self) -> BaseTrigger:
        """Get the trigger instance for this component.

        This method should return an instance of a class that inherits from BaseTrigger.
        The trigger service will use this instance to create subscriptions and check for events.
        """
