"""Test data factories and mock components for integration testing."""

import contextlib
import uuid
from typing import Any

from langflow.custom import Component
from langflow.schema.data import Data
from langflow.schema.message import Message


class TestDataFactory:
    """Factory for creating test data objects."""

    def __init__(self):
        self.counter = 0

    def get_unique_id(self) -> str:
        """Get a unique ID for test objects."""
        self.counter += 1
        return f"test_{self.counter}_{uuid.uuid4().hex[:8]}"

    def create_message(
        self,
        text: str = "test message",
        sender: str = "User",
        sender_name: str = "Test User",
        session_id: str | None = None,
        **kwargs,
    ) -> Message:
        """Create a test Message object."""
        return Message(
            text=text, sender=sender, sender_name=sender_name, session_id=session_id or self.get_unique_id(), **kwargs
        )

    def create_data(self, data: Any = None, text: str | None = None, **kwargs) -> Data:
        """Create a test Data object."""
        if data is None:
            data = {"test_key": "test_value", "id": self.get_unique_id()}

        return Data(data=data, text=text, **kwargs)

    def create_flow_data(self, name: str | None = None, description: str | None = None, **kwargs) -> dict[str, Any]:
        """Create test flow data for API testing."""
        flow_id = self.get_unique_id()

        return {
            "name": name or f"Test Flow {flow_id}",
            "description": description or f"Test flow created by integration test {flow_id}",
            "data": self.create_simple_flow_graph(),
            **kwargs,
        }

    def create_simple_flow_graph(self) -> dict[str, Any]:
        """Create a simple flow graph for testing."""
        return {
            "nodes": [
                {
                    "id": "input-1",
                    "type": "ChatInput",
                    "data": {
                        "type": "ChatInput",
                        "node": {
                            "template": {
                                "input_value": {"value": ""},
                                "sender": {"value": "User"},
                                "sender_name": {"value": "User"},
                            }
                        },
                    },
                    "position": {"x": 100, "y": 100},
                },
                {
                    "id": "output-1",
                    "type": "ChatOutput",
                    "data": {"type": "ChatOutput", "node": {"template": {"input_value": {"value": ""}}}},
                    "position": {"x": 300, "y": 100},
                },
            ],
            "edges": [
                {
                    "id": "edge-1",
                    "source": "input-1",
                    "target": "output-1",
                    "sourceHandle": "message",
                    "targetHandle": "input_value",
                }
            ],
        }

    def create_user_data(
        self, username: str | None = None, password: str = "testpassword123", **kwargs
    ) -> dict[str, Any]:
        """Create test user data."""
        user_id = self.get_unique_id()

        return {"username": username or f"testuser_{user_id}", "password": password, **kwargs}

    def create_api_key_data(self, name: str | None = None, **kwargs) -> dict[str, Any]:
        """Create test API key data."""
        key_id = self.get_unique_id()

        return {"name": name or f"test_api_key_{key_id}", **kwargs}

    def create_test_inputs(self, input_type: str = "text", count: int = 5) -> list[Any]:
        """Create a list of test inputs for parameterized testing."""
        if input_type == "text":
            return [
                "Hello world",
                "Test message",
                "",
                "A longer test message with more content",
                "Special chars: !@#$%^&*()",
            ][:count]
        if input_type == "json":
            return [
                {"key": "value"},
                {"nested": {"key": "value"}},
                {"list": [1, 2, 3]},
                {},
                {"complex": {"data": [{"item": i} for i in range(3)]}},
            ][:count]
        if input_type == "numbers":
            return [0, 1, -1, 42, 3.14159][:count]
        return [f"test_input_{i}" for i in range(count)]


class MockComponentFactory:
    """Factory for creating mock components for testing."""

    @staticmethod
    def create_echo_component() -> type[Component]:
        """Create a simple echo component that returns its input."""

        class EchoComponent(Component):
            display_name = "Echo"
            description = "Echoes input back as output"

            inputs = [{"name": "input_text", "type": "str", "display_name": "Input Text"}]

            outputs = [{"name": "output_text", "type": "str", "display_name": "Output Text"}]

            def build(self, input_text: str) -> str:
                return input_text

        return EchoComponent

    @staticmethod
    def create_delay_component(delay_seconds: float = 0.1) -> type[Component]:
        """Create a component that introduces a delay."""

        class DelayComponent(Component):
            display_name = "Delay"
            description = f"Adds {delay_seconds}s delay"

            inputs = [{"name": "input_value", "type": "str", "display_name": "Input"}]

            outputs = [{"name": "output_value", "type": "str", "display_name": "Output"}]

            async def build(self, input_value: str) -> str:
                import asyncio

                await asyncio.sleep(delay_seconds)
                return input_value

        return DelayComponent

    @staticmethod
    def create_error_component(error_message: str = "Test error") -> type[Component]:
        """Create a component that always raises an error."""

        class ErrorComponent(Component):
            display_name = "Error"
            description = "Always raises an error"

            inputs = [{"name": "input_value", "type": "str", "display_name": "Input"}]

            outputs = [{"name": "output_value", "type": "str", "display_name": "Output"}]

            def build(self, input_value: str) -> str:
                raise ValueError(error_message)

        return ErrorComponent

    @staticmethod
    def create_transformer_component(transform_func: callable | None = None) -> type[Component]:
        """Create a component that transforms input using a function."""
        if transform_func is None:

            def transform_func(x):
                return x.upper()

        class TransformerComponent(Component):
            display_name = "Transformer"
            description = "Transforms input using provided function"

            inputs = [{"name": "input_value", "type": "str", "display_name": "Input"}]

            outputs = [{"name": "output_value", "type": "str", "display_name": "Output"}]

            def build(self, input_value: str) -> str:
                return transform_func(input_value)

        return TransformerComponent

    @staticmethod
    def create_data_processor_component() -> type[Component]:
        """Create a component that processes Data objects."""

        class DataProcessorComponent(Component):
            display_name = "Data Processor"
            description = "Processes Data objects"

            inputs = [{"name": "input_data", "type": "Data", "display_name": "Input Data"}]

            outputs = [{"name": "output_data", "type": "Data", "display_name": "Output Data"}]

            def build(self, input_data: Data) -> Data:
                # Add a processed flag to the data
                processed_data = input_data.data.copy() if isinstance(input_data.data, dict) else input_data.data
                if isinstance(processed_data, dict):
                    processed_data["processed"] = True

                return Data(data=processed_data, text=input_data.text)

        return DataProcessorComponent


class MockExternalService:
    """Mock external service for testing components that depend on external APIs."""

    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses = responses or {}
        self.call_history = []

    def mock_api_call(self, endpoint: str, **kwargs) -> Any:
        """Mock an API call and return predefined response."""
        self.call_history.append({"endpoint": endpoint, "kwargs": kwargs})

        if endpoint in self.responses:
            return self.responses[endpoint]

        # Default responses
        if "error" in endpoint:
            msg = "Mock API error"
            raise Exception(msg)

        return {"status": "success", "data": "mock_data"}

    def get_call_count(self, endpoint: str) -> int:
        """Get number of calls made to specific endpoint."""
        return len([call for call in self.call_history if call["endpoint"] == endpoint])

    def reset_history(self):
        """Reset call history."""
        self.call_history = []


class TestEnvironmentManager:
    """Manages test environment setup and cleanup."""

    def __init__(self):
        self.temp_files = []
        self.temp_dirs = []
        self.cleanup_functions = []

    def add_temp_file(self, file_path: str):
        """Register a temporary file for cleanup."""
        self.temp_files.append(file_path)

    def add_temp_dir(self, dir_path: str):
        """Register a temporary directory for cleanup."""
        self.temp_dirs.append(dir_path)

    def add_cleanup_function(self, func: callable):
        """Register a cleanup function."""
        self.cleanup_functions.append(func)

    def cleanup(self):
        """Clean up all registered resources."""
        import os
        import shutil

        # Run cleanup functions
        for func in self.cleanup_functions:
            with contextlib.suppress(Exception):
                func()

        # Remove temp files
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

        # Remove temp directories
        for dir_path in self.temp_dirs:
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            except Exception:
                pass

        # Clear lists
        self.temp_files.clear()
        self.temp_dirs.clear()
        self.cleanup_functions.clear()
