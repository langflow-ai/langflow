"""Static model catalog for the Amazon Bedrock unified provider."""

from lfx.base.models.aws_constants import AWS_MODELS_DETAILED


def load_bedrock_catalog() -> list[dict]:
    return [dict(row) for row in AWS_MODELS_DETAILED]
