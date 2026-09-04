"""lfx-amazon: Amazon bundle.

Distribution unit ``lfx-amazon``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:amazon:<Class>@official``.
"""

from lfx_amazon.components.amazon.amazon_bedrock_converse import AmazonBedrockConverseComponent
from lfx_amazon.components.amazon.amazon_bedrock_embedding import AmazonBedrockEmbeddingsComponent
from lfx_amazon.components.amazon.amazon_bedrock_model import AmazonBedrockComponent
from lfx_amazon.components.amazon.s3_bucket_uploader import S3BucketUploaderComponent

__all__ = [
    "AmazonBedrockComponent",
    "AmazonBedrockConverseComponent",
    "AmazonBedrockEmbeddingsComponent",
    "S3BucketUploaderComponent",
]
