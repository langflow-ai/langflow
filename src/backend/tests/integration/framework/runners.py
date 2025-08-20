"""Test runners for components, flows, and APIs."""

import uuid
from typing import Any

from langflow.custom import Component
from langflow.graph import Graph

from tests.integration.utils import run_flow as _run_flow
from tests.integration.utils import run_single_component as _run_single_component


class ComponentRunner:
    """Enhanced component runner with additional utilities."""

    def __init__(self):
        self.default_session_id = str(uuid.uuid4())
        self.default_user_id = str(uuid.uuid4())

    async def run_single_component(
        self,
        component_class: type[Component],
        inputs: dict[str, Any] | None = None,
        run_input: Any = None,
        session_id: str | None = None,
        input_type: str = "chat",
        user_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Run a single component with enhanced error handling and logging.

        Args:
            component_class: Component class to test
            inputs: Input parameters for the component
            run_input: Input value to pass to the component
            session_id: Session ID for the run
            input_type: Type of input ("chat", "text", etc.)
            user_id: User ID for the component
            **kwargs: Additional arguments

        Returns:
            Dictionary of component outputs

        Raises:
            ComponentTestError: If component execution fails
        """
        try:
            return await _run_single_component(
                component_class,
                inputs=inputs,
                run_input=run_input,
                session_id=session_id or self.default_session_id,
                input_type=input_type,
                **kwargs,
            )
        except Exception as e:
            msg = f"Failed to run component {component_class.__name__}: {e}"
            raise ComponentTestError(msg) from e

    async def run_component_with_inputs(
        self, component_class: type[Component], input_combinations: list[dict[str, Any]], **kwargs
    ) -> list[dict[str, Any]]:
        """Run component with multiple input combinations.

        Args:
            component_class: Component class to test
            input_combinations: List of input dictionaries to test
            **kwargs: Additional arguments passed to run_single_component

        Returns:
            List of output dictionaries for each input combination
        """
        results = []
        for inputs in input_combinations:
            result = await self.run_single_component(component_class, inputs=inputs, **kwargs)
            results.append(result)
        return results

    async def run_component_chain(self, chain_config: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run a chain of components where output of one feeds into the next.

        Args:
            chain_config: List of component configurations
                Each config should have: {'component_class', 'inputs', 'output_key'}

        Returns:
            List of outputs from each component in the chain
        """
        results = []
        previous_output = None

        for config in chain_config:
            component_class = config["component_class"]
            inputs = config.get("inputs", {})

            # Use output from previous component if specified
            if previous_output and "input_from_previous" in config:
                input_key = config["input_from_previous"]
                output_key = config.get("output_key", next(iter(previous_output.keys())))
                inputs[input_key] = previous_output[output_key]

            result = await self.run_single_component(component_class, inputs=inputs)
            results.append(result)
            previous_output = result

        return results


class FlowRunner:
    """Enhanced flow runner with utilities for complex flow testing."""

    def __init__(self):
        self.default_session_id = str(uuid.uuid4())
        self.default_user_id = str(uuid.uuid4())

    async def run_flow(
        self, graph: Graph, run_input: Any = None, session_id: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Run a complete flow with enhanced error handling.

        Args:
            graph: Flow graph to execute
            run_input: Input to pass to the flow
            session_id: Session ID for the run
            **kwargs: Additional arguments

        Returns:
            Dictionary of flow outputs

        Raises:
            FlowTestError: If flow execution fails
        """
        try:
            return await _run_flow(graph, run_input=run_input, session_id=session_id or self.default_session_id)
        except Exception as e:
            msg = f"Failed to run flow: {e}"
            raise FlowTestError(msg) from e

    async def run_flow_with_multiple_inputs(self, graph: Graph, inputs: list[Any], **kwargs) -> list[dict[str, Any]]:
        """Run flow with multiple different inputs.

        Args:
            graph: Flow graph to execute
            inputs: List of inputs to test with
            **kwargs: Additional arguments

        Returns:
            List of output dictionaries for each input
        """
        results = []
        for input_value in inputs:
            result = await self.run_flow(graph, run_input=input_value, **kwargs)
            results.append(result)
        return results

    def build_linear_flow(self, components: list[type[Component]]) -> Graph:
        """Build a linear flow connecting components in sequence.

        Args:
            components: List of component classes to connect

        Returns:
            Graph with components connected linearly
        """
        if len(components) < 2:
            msg = "Need at least 2 components for a linear flow"
            raise ValueError(msg)

        graph = Graph(user_id=self.default_user_id)
        component_ids = []

        # Add all components
        for component_class in components:
            component = component_class(_user_id=self.default_user_id)
            component_id = graph.add_component(component)
            component_ids.append(component_id)

        # Connect components linearly
        for i in range(len(component_ids) - 1):
            current_id = component_ids[i]
            next_id = component_ids[i + 1]

            # Get the first output of current and first input of next
            current_component = graph.get_vertex(current_id).component
            next_component = graph.get_vertex(next_id).component

            if current_component.outputs and next_component.inputs:
                output_name = current_component.outputs[0].name
                input_name = next_component.inputs[0].name

                graph.add_component_edge(current_id, (output_name, input_name), next_id)

        return graph


class APITestRunner:
    """Runner for API integration tests."""

    def __init__(self):
        self.base_url = "http://testserver"
        self.default_headers = {"Content-Type": "application/json"}

    async def make_request(self, client, method: str, url: str, headers: dict[str, str] | None = None, **kwargs):
        """Make HTTP request with enhanced error handling.

        Args:
            client: HTTP client (from fixtures)
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Request headers
            **kwargs: Additional request arguments

        Returns:
            HTTP response

        Raises:
            APITestError: If request fails unexpectedly
        """
        merged_headers = {**self.default_headers, **(headers or {})}

        try:
            return await getattr(client, method.lower())(url, headers=merged_headers, **kwargs)
        except Exception as e:
            msg = f"API request failed: {method} {url} - {e}"
            raise APITestError(msg) from e

    async def test_endpoint_crud_cycle(
        self,
        client,
        base_endpoint: str,
        create_data: dict[str, Any],
        update_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Test complete CRUD cycle for an endpoint.

        Args:
            client: HTTP client
            base_endpoint: Base API endpoint (e.g., "/api/v1/flows")
            create_data: Data for creating resource
            update_data: Data for updating resource (optional)
            headers: Request headers

        Returns:
            Dictionary with results from each CRUD operation
        """
        results = {}

        # CREATE
        create_response = await self.make_request(client, "POST", base_endpoint, headers=headers, json=create_data)
        assert create_response.status_code in [200, 201], f"Create failed: {create_response.text}"
        created_item = create_response.json()
        results["create"] = created_item

        # READ
        item_id = created_item.get("id")
        if item_id:
            read_response = await self.make_request(client, "GET", f"{base_endpoint}/{item_id}", headers=headers)
            assert read_response.status_code == 200, f"Read failed: {read_response.text}"
            results["read"] = read_response.json()

        # UPDATE (if update data provided)
        if update_data and item_id:
            update_response = await self.make_request(
                client, "PUT", f"{base_endpoint}/{item_id}", headers=headers, json=update_data
            )
            assert update_response.status_code == 200, f"Update failed: {update_response.text}"
            results["update"] = update_response.json()

        # DELETE
        if item_id:
            delete_response = await self.make_request(client, "DELETE", f"{base_endpoint}/{item_id}", headers=headers)
            assert delete_response.status_code in [200, 204], f"Delete failed: {delete_response.text}"
            results["delete"] = True

        return results


# Custom exception classes for better error handling
class ComponentTestError(Exception):
    """Raised when component testing fails."""


class FlowTestError(Exception):
    """Raised when flow testing fails."""


class APITestError(Exception):
    """Raised when API testing fails."""
