from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.amazon.amazon_bedrock_embedding import AmazonBedrockEmbeddingsComponent
    from lfx.components.amazon.amazon_bedrock_model import AmazonBedrockComponent
    from lfx.components.amazon.s3_bucket_uploader import S3BucketUploaderComponent

_dynamic_imports = {
    "AmazonBedrockEmbeddingsComponent": "amazon_bedrock_embedding",
    "AmazonBedrockComponent": "amazon_bedrock_model",
    "S3BucketUploaderComponent": "s3_bucket_uploader",
}

__all__ = ["AmazonBedrockComponent", "AmazonBedrockEmbeddingsComponent", "S3BucketUploaderComponent"]


def __getattr__(attr_name: str) -> Any:
    """Lazily import amazon components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
