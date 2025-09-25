"""Comprehensive unit tests for telemetry schema classes.

Testing library and framework: pytest
"""

import pytest
from langflow.services.telemetry.schema import (
    ComponentPayload,
    PlaygroundPayload,
    RunPayload,
    ShutdownPayload,
    VersionPayload,
)


class TestRunPayload:
    """Test cases for RunPayload."""

    def test_run_payload_initialization_with_valid_data(self):
        """Test RunPayload initialization with valid parameters."""
        payload = RunPayload(
            run_is_webhook=True, run_seconds=120, run_success=True, run_error_message="", client_type="oss"
        )

        assert payload.run_is_webhook is True
        assert payload.run_seconds == 120
        assert payload.run_success is True
        assert payload.run_error_message == ""
        assert payload.client_type == "oss"

    def test_run_payload_initialization_with_defaults(self):
        """Test RunPayload initialization with default values."""
        payload = RunPayload(run_seconds=60, run_success=False, run_error_message="Test error")

        assert payload.run_is_webhook is False  # Default value
        assert payload.run_seconds == 60
        assert payload.run_success is False
        assert payload.run_error_message == "Test error"
        assert payload.client_type is None  # Default value

    def test_run_payload_serialization(self):
        """Test RunPayload serialization to dictionary."""
        payload = RunPayload(
            run_is_webhook=True, run_seconds=180, run_success=True, run_error_message="", client_type="desktop"
        )

        data = payload.model_dump(by_alias=True)

        assert data["runIsWebhook"] is True
        assert data["runSeconds"] == 180
        assert data["runSuccess"] is True
        assert data["runErrorMessage"] == ""
        assert data["clientType"] == "desktop"

    def test_run_payload_with_negative_seconds(self):
        """Test RunPayload accepts negative seconds (no validation in schema)."""
        payload = RunPayload(run_seconds=-10, run_success=True)
        assert payload.run_seconds == -10
        assert payload.run_success is True

    def test_run_payload_with_long_error_message(self):
        """Test RunPayload with long error message."""
        long_error = "x" * 1000
        payload = RunPayload(run_seconds=30, run_success=False, run_error_message=long_error, client_type="oss")

        assert payload.run_error_message == long_error
        assert len(payload.run_error_message) == 1000


class TestShutdownPayload:
    """Test cases for ShutdownPayload."""

    def test_shutdown_payload_initialization(self):
        """Test ShutdownPayload initialization with valid parameters."""
        payload = ShutdownPayload(time_running=3600, client_type="oss")

        assert payload.time_running == 3600
        assert payload.client_type == "oss"

    def test_shutdown_payload_initialization_without_client_type(self):
        """Test ShutdownPayload initialization without client_type."""
        payload = ShutdownPayload(time_running=1800)

        assert payload.time_running == 1800
        assert payload.client_type is None

    def test_shutdown_payload_serialization(self):
        """Test ShutdownPayload serialization to dictionary."""
        payload = ShutdownPayload(time_running=7200, client_type="desktop")

        data = payload.model_dump(by_alias=True)

        assert data["timeRunning"] == 7200
        assert data["clientType"] == "desktop"

    def test_shutdown_payload_with_negative_time(self):
        """Test ShutdownPayload accepts negative time (no validation in schema)."""
        payload = ShutdownPayload(time_running=-100)
        assert payload.time_running == -100

    def test_shutdown_payload_with_zero_time(self):
        """Test ShutdownPayload with zero time running."""
        payload = ShutdownPayload(time_running=0)
        assert payload.time_running == 0


class TestVersionPayload:
    """Test cases for VersionPayload."""

    def test_version_payload_initialization(self):
        """Test VersionPayload initialization with valid parameters."""
        payload = VersionPayload(
            package="langflow",
            version="1.0.0",
            platform="Linux-5.4.0",
            python="3.9",
            arch="x86_64",
            auto_login=False,
            cache_type="memory",
            backend_only=False,
            client_type="oss",
        )

        assert payload.package == "langflow"
        assert payload.version == "1.0.0"
        assert payload.platform == "Linux-5.4.0"
        assert payload.python == "3.9"
        assert payload.arch == "x86_64"
        assert payload.auto_login is False
        assert payload.cache_type == "memory"
        assert payload.backend_only is False
        assert payload.client_type == "oss"

    def test_version_payload_initialization_with_all_required_fields(self):
        """Test VersionPayload initialization with all required fields."""
        payload = VersionPayload(
            package="langflow",
            version="1.0.0",
            platform="Windows",
            python="3.8",
            arch="x86_64",
            auto_login=True,
            cache_type="redis",
            backend_only=True,
        )

        assert payload.package == "langflow"
        assert payload.version == "1.0.0"
        assert payload.client_type is None  # Default value

    def test_version_payload_serialization(self):
        """Test VersionPayload serialization to dictionary."""
        payload = VersionPayload(
            package="langflow",
            version="1.5.2",
            platform="macOS-12.0",
            python="3.10",
            arch="arm64",
            auto_login=True,
            cache_type="redis",
            backend_only=True,
            client_type="desktop",
        )

        data = payload.model_dump(by_alias=True)

        assert data["package"] == "langflow"
        assert data["version"] == "1.5.2"
        assert data["platform"] == "macOS-12.0"
        assert data["python"] == "3.10"
        assert data["arch"] == "arm64"
        assert data["autoLogin"] is True
        assert data["cacheType"] == "redis"
        assert data["backendOnly"] is True
        assert data["clientType"] == "desktop"

    def test_version_payload_with_special_characters(self):
        """Test VersionPayload with special characters in strings."""
        payload = VersionPayload(
            package="langflow-dev",
            version="1.0.0-beta.1",
            platform="Windows 10 Pro",
            python="3.9.7",
            arch="x86_64",
            auto_login=False,
            cache_type="memory",
            backend_only=False,
        )

        assert payload.package == "langflow-dev"
        assert payload.version == "1.0.0-beta.1"
        assert payload.platform == "Windows 10 Pro"


class TestPlaygroundPayload:
    """Test cases for PlaygroundPayload."""

    def test_playground_payload_initialization(self):
        """Test PlaygroundPayload initialization with valid parameters."""
        payload = PlaygroundPayload(
            playground_seconds=45,
            playground_component_count=5,
            playground_success=True,
            playground_error_message="",
            client_type="oss",
        )

        assert payload.playground_seconds == 45
        assert payload.playground_component_count == 5
        assert payload.playground_success is True
        assert payload.playground_error_message == ""
        assert payload.client_type == "oss"

    def test_playground_payload_initialization_with_none_component_count(self):
        """Test PlaygroundPayload initialization with None component count."""
        payload = PlaygroundPayload(playground_seconds=30, playground_component_count=None, playground_success=True)

        assert payload.playground_seconds == 30
        assert payload.playground_component_count is None
        assert payload.playground_success is True

    def test_playground_payload_serialization(self):
        """Test PlaygroundPayload serialization to dictionary."""
        payload = PlaygroundPayload(
            playground_seconds=60,
            playground_component_count=10,
            playground_success=False,
            playground_error_message="Component failed",
            client_type="desktop",
        )

        data = payload.model_dump(by_alias=True)

        assert data["playgroundSeconds"] == 60
        assert data["playgroundComponentCount"] == 10
        assert data["playgroundSuccess"] is False
        assert data["playgroundErrorMessage"] == "Component failed"
        assert data["clientType"] == "desktop"

    def test_playground_payload_with_negative_seconds(self):
        """Test PlaygroundPayload accepts negative seconds (no validation in schema)."""
        payload = PlaygroundPayload(playground_seconds=-10, playground_success=True)
        assert payload.playground_seconds == -10
        assert payload.playground_success is True

    def test_playground_payload_with_negative_component_count(self):
        """Test PlaygroundPayload accepts negative component count (no validation in schema)."""
        payload = PlaygroundPayload(playground_seconds=30, playground_component_count=-5, playground_success=True)
        assert payload.playground_component_count == -5
        assert payload.playground_success is True

    def test_playground_payload_with_failed_execution(self):
        """Test PlaygroundPayload with failed execution."""
        payload = PlaygroundPayload(
            playground_seconds=15,
            playground_component_count=3,
            playground_success=False,
            playground_error_message="Timeout occurred",
            client_type="oss",
        )

        assert payload.playground_success is False
        assert payload.playground_error_message == "Timeout occurred"


class TestComponentPayload:
    """Test cases for ComponentPayload."""

    def test_component_payload_initialization(self):
        """Test ComponentPayload initialization with valid parameters."""
        payload = ComponentPayload(
            component_name="TextInput",
            component_seconds=2,
            component_success=True,
            component_error_message=None,
            client_type="oss",
        )

        assert payload.component_name == "TextInput"
        assert payload.component_seconds == 2
        assert payload.component_success is True
        assert payload.component_error_message is None
        assert payload.client_type == "oss"

    def test_component_payload_initialization_with_error(self):
        """Test ComponentPayload initialization with error message."""
        payload = ComponentPayload(
            component_name="LLMChain",
            component_seconds=5,
            component_success=False,
            component_error_message="API rate limit exceeded",
            client_type="desktop",
        )

        assert payload.component_name == "LLMChain"
        assert payload.component_seconds == 5
        assert payload.component_success is False
        assert payload.component_error_message == "API rate limit exceeded"
        assert payload.client_type == "desktop"

    def test_component_payload_serialization(self):
        """Test ComponentPayload serialization to dictionary."""
        payload = ComponentPayload(
            component_name="OpenAI",
            component_seconds=3,
            component_success=True,
            component_error_message=None,
            client_type="oss",
        )

        data = payload.model_dump(by_alias=True)

        assert data["componentName"] == "OpenAI"
        assert data["componentSeconds"] == 3
        assert data["componentSuccess"] is True
        assert data["componentErrorMessage"] is None
        assert data["clientType"] == "oss"

    def test_component_payload_with_negative_seconds(self):
        """Test ComponentPayload accepts negative seconds (no validation in schema)."""
        payload = ComponentPayload(
            component_name="TestComponent", component_seconds=-1, component_success=True, component_error_message=None
        )
        assert payload.component_seconds == -1
        assert payload.component_success is True

    def test_component_payload_with_empty_name(self):
        """Test ComponentPayload with empty component name."""
        payload = ComponentPayload(
            component_name="", component_seconds=1, component_success=True, component_error_message=None
        )
        assert payload.component_name == ""
        assert payload.component_success is True

    def test_component_payload_with_special_characters_in_name(self):
        """Test ComponentPayload with special characters in component name."""
        payload = ComponentPayload(
            component_name="Custom-Component_v1.0",
            component_seconds=1,
            component_success=True,
            component_error_message=None,
        )

        assert payload.component_name == "Custom-Component_v1.0"


class TestPayloadEdgeCases:
    """Test edge cases and boundary conditions for all payloads."""

    def test_run_payload_with_extremely_large_values(self):
        """Test RunPayload with extremely large values."""
        large_seconds = 2**31 - 1  # Max int32 value

        payload = RunPayload(run_seconds=large_seconds, run_success=True, run_error_message="x" * 10000)

        assert payload.run_seconds == large_seconds
        assert len(payload.run_error_message) == 10000

    def test_shutdown_payload_with_maximum_time(self):
        """Test ShutdownPayload with maximum time value."""
        max_time = 2**31 - 1

        payload = ShutdownPayload(time_running=max_time)
        assert payload.time_running == max_time

    def test_version_payload_with_unicode_strings(self):
        """Test VersionPayload with unicode strings."""
        payload = VersionPayload(
            package="langflow-🚀",
            version="1.0.0-测试",
            platform="Linux-测试系统",
            python="3.9",
            arch="x86_64",
            auto_login=False,
            cache_type="memory",
            backend_only=False,
        )

        assert payload.package == "langflow-🚀"
        assert payload.version == "1.0.0-测试"
        assert payload.platform == "Linux-测试系统"

    def test_playground_payload_with_zero_values(self):
        """Test PlaygroundPayload with zero values."""
        payload = PlaygroundPayload(playground_seconds=0, playground_component_count=0, playground_success=True)

        assert payload.playground_seconds == 0
        assert payload.playground_component_count == 0

    def test_component_payload_with_very_long_name(self):
        """Test ComponentPayload with very long component name."""
        long_name = "x" * 1000

        payload = ComponentPayload(
            component_name=long_name, component_seconds=1, component_success=True, component_error_message=None
        )

        assert payload.component_name == long_name
        assert len(payload.component_name) == 1000

    @pytest.mark.parametrize("client_type", ["oss", "desktop", "cloud", "enterprise", "custom"])
    def test_all_payloads_with_different_client_types(self, client_type):
        """Test all payloads with different client types."""
        # Test RunPayload
        run_payload = RunPayload(run_seconds=60, run_success=True, client_type=client_type)
        assert run_payload.client_type == client_type

        # Test ShutdownPayload
        shutdown_payload = ShutdownPayload(time_running=3600, client_type=client_type)
        assert shutdown_payload.client_type == client_type

        # Test VersionPayload
        version_payload = VersionPayload(
            package="langflow",
            version="1.0.0",
            platform="Linux",
            python="3.9",
            arch="x86_64",
            auto_login=False,
            cache_type="memory",
            backend_only=False,
            client_type=client_type,
        )
        assert version_payload.client_type == client_type

        # Test PlaygroundPayload
        playground_payload = PlaygroundPayload(playground_seconds=30, playground_success=True, client_type=client_type)
        assert playground_payload.client_type == client_type

        # Test ComponentPayload
        component_payload = ComponentPayload(
            component_name="TestComponent",
            component_seconds=1,
            component_success=True,
            component_error_message=None,
            client_type=client_type,
        )
        assert component_payload.client_type == client_type

    def test_payload_serialization_with_none_values(self):
        """Test payload serialization when optional fields are None."""
        # Test with client_type as None
        run_payload = RunPayload(run_seconds=60, run_success=True, client_type=None)

        data = run_payload.model_dump(by_alias=True, exclude_none=True)
        assert "clientType" not in data  # Should be excluded when None

    def test_payload_serialization_with_empty_strings(self):
        """Test payload serialization with empty strings."""
        run_payload = RunPayload(
            run_seconds=60,
            run_success=True,
            run_error_message="",
            client_type="oss",  # Empty string
        )

        data = run_payload.model_dump(by_alias=True)
        assert data["runErrorMessage"] == ""

    def test_payload_validation_with_invalid_types(self):
        """Test payload validation with invalid data types."""
        # Test RunPayload with string instead of int
        with pytest.raises((ValueError, TypeError)):
            RunPayload(run_seconds="not_a_number", run_success=True)

        # Test with boolean instead of string for error message
        with pytest.raises((ValueError, TypeError)):
            RunPayload(run_seconds=60, run_success=True, run_error_message=True)


class TestPayloadIntegration:
    """Integration tests for payload interactions."""

    def test_payload_workflow_simulation(self):
        """Simulate a complete telemetry workflow with all payload types."""
        # 1. Version payload (startup)
        version_payload = VersionPayload(
            package="langflow",
            version="1.0.0",
            platform="Linux",
            python="3.9",
            arch="x86_64",
            auto_login=False,
            cache_type="memory",
            backend_only=False,
            client_type="oss",
        )

        # 2. Run payload (flow execution)
        run_payload = RunPayload(run_seconds=120, run_success=True, client_type="oss")

        # 3. Component payloads (individual components)
        component_payloads = [
            ComponentPayload(
                component_name="TextInput",
                component_seconds=1,
                component_success=True,
                component_error_message=None,
                client_type="oss",
            ),
            ComponentPayload(
                component_name="OpenAI",
                component_seconds=5,
                component_success=True,
                component_error_message=None,
                client_type="oss",
            ),
            ComponentPayload(
                component_name="TextOutput",
                component_seconds=1,
                component_success=True,
                component_error_message=None,
                client_type="oss",
            ),
        ]

        # 4. Playground payload (testing)
        playground_payload = PlaygroundPayload(
            playground_seconds=30, playground_component_count=3, playground_success=True, client_type="oss"
        )

        # 5. Shutdown payload (cleanup)
        shutdown_payload = ShutdownPayload(time_running=3600, client_type="oss")

        # Verify all payloads have consistent client_type
        all_payloads = [version_payload, run_payload, playground_payload, shutdown_payload, *component_payloads]
        client_types = [p.client_type for p in all_payloads]
        assert all(ct == "oss" for ct in client_types)

        # Verify timing consistency
        total_component_time = sum(cp.component_seconds for cp in component_payloads)
        assert total_component_time <= run_payload.run_seconds

    def test_error_propagation_workflow(self):
        """Test error propagation through different payload types."""
        # Component that fails
        failed_component = ComponentPayload(
            component_name="OpenAI",
            component_seconds=5,
            component_success=False,
            component_error_message="API rate limit exceeded",
            client_type="oss",
        )

        # Run fails due to component failure
        failed_run = RunPayload(
            run_seconds=10,
            run_success=False,
            run_error_message="Component 'OpenAI' failed: API rate limit exceeded",
            client_type="oss",
        )

        # Playground fails
        failed_playground = PlaygroundPayload(
            playground_seconds=30,
            playground_component_count=1,
            playground_success=False,
            playground_error_message="Test failed due to component error",
            client_type="oss",
        )

        # Verify error consistency
        assert not failed_component.component_success
        assert not failed_run.run_success
        assert not failed_playground.playground_success
        assert "API rate limit exceeded" in failed_component.component_error_message
        assert "API rate limit exceeded" in failed_run.run_error_message


# Test configuration and fixtures
@pytest.fixture
def sample_run_payload():
    """Fixture providing sample run payload for tests."""
    return RunPayload(run_is_webhook=False, run_seconds=120, run_success=True, run_error_message="", client_type="oss")


@pytest.fixture
def sample_shutdown_payload():
    """Fixture providing sample shutdown payload for tests."""
    return ShutdownPayload(time_running=3600, client_type="oss")


@pytest.fixture
def sample_version_payload():
    """Fixture providing sample version payload for tests."""
    return VersionPayload(
        package="langflow",
        version="1.0.0",
        platform="Linux-5.4.0",
        python="3.9",
        arch="x86_64",
        auto_login=False,
        cache_type="memory",
        backend_only=False,
        client_type="oss",
    )


@pytest.fixture
def sample_playground_payload():
    """Fixture providing sample playground payload for tests."""
    return PlaygroundPayload(
        playground_seconds=45,
        playground_component_count=5,
        playground_success=True,
        playground_error_message="",
        client_type="oss",
    )


@pytest.fixture
def sample_component_payload():
    """Fixture providing sample component payload for tests."""
    return ComponentPayload(
        component_name="TextInput",
        component_seconds=2,
        component_success=True,
        component_error_message=None,
        client_type="oss",
    )


# Performance and stress tests
class TestPayloadPerformance:
    """Performance tests for payload operations."""

    def test_payload_creation_performance(self):
        """Test performance of creating many payload objects."""
        import time

        start_time = time.time()

        # Create 1000 payload objects
        payloads = []
        for i in range(1000):
            payload = RunPayload(run_seconds=i, run_success=True, client_type="oss")
            payloads.append(payload)

        creation_time = time.time() - start_time

        # Should create 1000 objects reasonably quickly (under 1 second)
        assert creation_time < 1.0
        assert len(payloads) == 1000

    def test_payload_serialization_performance(self):
        """Test performance of serializing payload objects."""
        import time

        # Create complex payload
        payload = VersionPayload(
            package="langflow",
            version="1.0.0",
            platform="Linux-5.4.0-x86_64-with-glibc2.31",
            python="3.9.7",
            arch="x86_64",
            auto_login=True,
            cache_type="redis",
            backend_only=False,
            client_type="oss",
        )

        start_time = time.time()

        # Serialize 1000 times
        for _ in range(1000):
            data = payload.model_dump(by_alias=True)
            assert len(data) > 0

        serialization_time = time.time() - start_time

        # Should serialize 1000 objects reasonably quickly
        assert serialization_time < 2.0


if __name__ == "__main__":
    pytest.main([__file__])
