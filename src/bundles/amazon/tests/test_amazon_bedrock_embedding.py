"""Regression test: the credentials profile builds the boto3 session and is not passed next to the client."""

from unittest.mock import patch

from lfx_amazon.components.amazon.amazon_bedrock_embedding import AmazonBedrockEmbeddingsComponent


def test_profile_builds_the_session_and_only_the_client_reaches_bedrock_embeddings():
    # BedrockEmbeddings applies credentials_profile_name only when client is None,
    # so passing it next to the pre-built client was a silent no-op.
    component = AmazonBedrockEmbeddingsComponent(
        model_id="amazon.titan-embed-text-v1",
        aws_access_key_id=None,
        aws_secret_access_key=None,
        aws_session_token=None,
        credentials_profile_name="my-profile",
        region_name="us-east-1",
    )
    with patch("boto3.Session") as session:
        embeddings = component.build_embeddings()

    session.assert_called_once_with(profile_name="my-profile")
    assert embeddings.client is session.return_value.client.return_value
    assert embeddings.credentials_profile_name is None
