"""Tests for AmazonBedrockEmbeddingsComponent.

This test module validates that the component wires AWS credentials into
``BedrockEmbeddings`` correctly:
- The boto3 session honors ``credentials_profile_name``.
- A pre-built client is forwarded to ``BedrockEmbeddings``.
- ``credentials_profile_name`` is NOT also passed alongside the client, since
  ``BedrockEmbeddings`` only applies it when ``client is None`` (passing both is
  a silent no-op). This mirrors the sibling LLM component, which passes only the
  client.
"""

from unittest.mock import MagicMock, patch

import pytest
from lfx.components.amazon.amazon_bedrock_embedding import AmazonBedrockEmbeddingsComponent

from tests.base import ComponentTestBaseWithoutClient


class TestAmazonBedrockEmbeddingsComponent(ComponentTestBaseWithoutClient):
    """Tests for the AmazonBedrockEmbeddingsComponent."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return AmazonBedrockEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "model_id": "amazon.titan-embed-text-v1",
            "aws_access_key_id": None,
            "aws_secret_access_key": None,
            "aws_session_token": None,
            "credentials_profile_name": "my-profile",
            "region_name": "us-east-1",
            "endpoint_url": None,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return []

    # =========================================================================
    # Build Embeddings Tests
    # =========================================================================

    @patch("boto3.Session")
    @patch("langchain_aws.BedrockEmbeddings")
    def test_build_embeddings_uses_profile_session(
        self, mock_bedrock_embeddings, mock_session, component_class, default_kwargs
    ):
        """Test that the boto3 session is created from credentials_profile_name."""
        mock_instance = MagicMock()
        mock_bedrock_embeddings.return_value = mock_instance
        mock_session.return_value.client.return_value = MagicMock()

        component = component_class(**default_kwargs)
        result = component.build_embeddings()

        # The profile is honored when constructing the session.
        mock_session.assert_called_once_with(profile_name="my-profile")
        assert result == mock_instance

    @patch("boto3.Session")
    @patch("langchain_aws.BedrockEmbeddings")
    def test_build_embeddings_does_not_pass_credentials_profile_name(
        self, mock_bedrock_embeddings, mock_session, component_class, default_kwargs
    ):
        """Regression test: credentials_profile_name must not be passed alongside client.

        ``BedrockEmbeddings`` only applies ``credentials_profile_name`` when
        ``client is None``. Passing both an explicit client and the profile is a
        silent no-op, so the component should forward only the pre-built client.
        """
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        component = component_class(**default_kwargs)
        component.build_embeddings()

        call_kwargs = mock_bedrock_embeddings.call_args.kwargs
        # The pre-built client (already created from the profile) is forwarded.
        assert call_kwargs["client"] is mock_client
        # The redundant profile kwarg must NOT be passed (it would be a no-op).
        assert "credentials_profile_name" not in call_kwargs

    @patch("boto3.Session")
    @patch("langchain_aws.BedrockEmbeddings")
    def test_build_embeddings_uses_explicit_keys_over_profile(
        self, mock_bedrock_embeddings, mock_session, component_class, default_kwargs
    ):
        """Test that explicit access keys take precedence over the profile."""
        mock_session.return_value.client.return_value = MagicMock()

        kwargs = {
            **default_kwargs,
            "aws_access_key_id": "test_access_key",
            "aws_secret_access_key": "test_secret",  # pragma: allowlist secret
        }
        component = component_class(**kwargs)
        component.build_embeddings()

        # Explicit keys build the session; profile is not used.
        mock_session.assert_called_once_with(
            aws_access_key_id="test_access_key",
            aws_secret_access_key="test_secret",  # pragma: allowlist secret  # noqa: S106
            aws_session_token=None,
        )
        mock_bedrock_embeddings.assert_called_once()

    # =========================================================================
    # Metadata Tests
    # =========================================================================

    def test_component_metadata(self, component_class):
        """Test that component metadata is correctly defined."""
        component = component_class()
        assert component.display_name == "Amazon Bedrock Embeddings"
        assert component.name == "AmazonBedrockEmbeddings"
        assert component.icon == "Amazon"

    def test_component_outputs(self, component_class):
        """Test that component has expected outputs."""
        component = component_class()
        output_names = [out.name for out in component.outputs]
        assert "embeddings" in output_names
