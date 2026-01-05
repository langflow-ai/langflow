"""Unit tests for langflow.core.celeryconfig module."""

# Import the module to test
from langflow.core import celeryconfig


class TestCeleryConfigAcceptContent:
    """Unit tests for accept_content configuration."""

    def test_accept_content_configuration(self):
        """Test that accept_content is set to the expected values."""
        # This should be consistent regardless of environment
        expected_content = ["json", "pickle"]
        assert celeryconfig.accept_content == expected_content

    def test_accept_content_types(self):
        """Test that accept_content contains the expected content types."""
        assert "json" in celeryconfig.accept_content
        assert "pickle" in celeryconfig.accept_content
        assert len(celeryconfig.accept_content) == 2

    def test_accept_content_is_list(self):
        """Test that accept_content is a list type."""
        assert isinstance(celeryconfig.accept_content, list)

    def test_accept_content_contains_strings(self):
        """Test that accept_content contains only string values."""
        for content_type in celeryconfig.accept_content:
            assert isinstance(content_type, str)


class TestCeleryConfigVariables:
    """Unit tests for configuration variables."""

    def test_required_config_variables_exist(self):
        """Test that all required configuration variables are defined."""
        required_vars = ["broker_url", "result_backend", "accept_content"]
        for var in required_vars:
            assert hasattr(celeryconfig, var), f"Missing required config variable: {var}"

    def test_config_variables_have_expected_types(self):
        """Test that configuration variables have the expected types."""
        assert isinstance(celeryconfig.broker_url, str)
        assert isinstance(celeryconfig.result_backend, str)
        assert isinstance(celeryconfig.accept_content, list)

    def test_broker_url_format(self):
        """Test that broker_url follows expected format."""
        broker_url = celeryconfig.broker_url
        # Should be either Redis or RabbitMQ format
        assert broker_url.startswith(("redis://", "amqp://")), f"Unexpected broker_url format: {broker_url}"

    def test_result_backend_format(self):
        """Test that result_backend follows expected format."""
        result_backend = celeryconfig.result_backend
        # Should be Redis format
        assert result_backend.startswith("redis://"), f"Unexpected result_backend format: {result_backend}"

    def test_broker_url_not_empty(self):
        """Test that broker_url is not an empty string."""
        assert len(celeryconfig.broker_url) > 0

    def test_result_backend_not_empty(self):
        """Test that result_backend is not an empty string."""
        assert len(celeryconfig.result_backend) > 0


class TestCeleryConfigStructure:
    """Unit tests for configuration structure."""

    def test_broker_url_contains_protocol(self):
        """Test that broker_url contains a valid protocol."""
        broker_url = celeryconfig.broker_url
        assert "://" in broker_url

    def test_result_backend_contains_protocol(self):
        """Test that result_backend contains a valid protocol."""
        result_backend = celeryconfig.result_backend
        assert "://" in result_backend

    def test_broker_url_contains_host(self):
        """Test that broker_url contains a host component."""
        broker_url = celeryconfig.broker_url
        # Remove protocol part
        if "://" in broker_url:
            host_part = broker_url.split("://")[1]
            assert len(host_part) > 0

    def test_result_backend_contains_host(self):
        """Test that result_backend contains a host component."""
        result_backend = celeryconfig.result_backend
        # Remove protocol part
        if "://" in result_backend:
            host_part = result_backend.split("://")[1]
            assert len(host_part) > 0
