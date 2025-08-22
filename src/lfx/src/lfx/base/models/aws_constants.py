from .model_metadata import create_model_metadata

# Unified model metadata - single source of truth
AWS_MODELS_DETAILED = [
    # Amazon Titan Models
    create_model_metadata(
        provider="Amazon Bedrock", name="amazon.titan-text-express-v1", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="amazon.titan-text-lite-v1", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="amazon.titan-text-premier-v1:0", icon="Amazon", tool_calling=True
    ),
    # Anthropic Models
    create_model_metadata(provider="Amazon Bedrock", name="anthropic.claude-v2", icon="Amazon", tool_calling=True),
    create_model_metadata(provider="Amazon Bedrock", name="anthropic.claude-v2:1", icon="Amazon", tool_calling=True),
    create_model_metadata(
        provider="Amazon Bedrock", name="anthropic.claude-3-sonnet-20240229-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="anthropic.claude-3-5-sonnet-20240620-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="anthropic.claude-3-5-sonnet-20241022-v2:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="anthropic.claude-3-haiku-20240307-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="anthropic.claude-3-5-haiku-20241022-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="anthropic.claude-3-opus-20240229-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="anthropic.claude-instant-v1", icon="Amazon", tool_calling=True
    ),
    # AI21 Labs Models
    create_model_metadata(provider="Amazon Bedrock", name="ai21.jamba-instruct-v1:0", icon="Amazon", tool_calling=True),
    create_model_metadata(provider="Amazon Bedrock", name="ai21.j2-mid-v1", icon="Amazon", tool_calling=True),
    create_model_metadata(provider="Amazon Bedrock", name="ai21.j2-ultra-v1", icon="Amazon", tool_calling=True),
    create_model_metadata(
        provider="Amazon Bedrock", name="ai21.jamba-1-5-large-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(provider="Amazon Bedrock", name="ai21.jamba-1-5-mini-v1:0", icon="Amazon", tool_calling=True),
    # Cohere Models
    create_model_metadata(provider="Amazon Bedrock", name="cohere.command-text-v14", icon="Amazon", tool_calling=True),
    create_model_metadata(
        provider="Amazon Bedrock", name="cohere.command-light-text-v14", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(provider="Amazon Bedrock", name="cohere.command-r-v1:0", icon="Amazon", tool_calling=True),
    create_model_metadata(
        provider="Amazon Bedrock", name="cohere.command-r-plus-v1:0", icon="Amazon", tool_calling=True
    ),
    # Meta Models
    create_model_metadata(provider="Amazon Bedrock", name="meta.llama2-13b-chat-v1", icon="Amazon", tool_calling=True),
    create_model_metadata(provider="Amazon Bedrock", name="meta.llama2-70b-chat-v1", icon="Amazon", tool_calling=True),
    create_model_metadata(
        provider="Amazon Bedrock", name="meta.llama3-8b-instruct-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="meta.llama3-70b-instruct-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="meta.llama3-1-8b-instruct-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="meta.llama3-1-70b-instruct-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="meta.llama3-1-405b-instruct-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="meta.llama3-2-1b-instruct-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="meta.llama3-2-3b-instruct-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="meta.llama3-2-11b-instruct-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="meta.llama3-2-90b-instruct-v1:0", icon="Amazon", tool_calling=True
    ),
    # Mistral AI Models
    create_model_metadata(
        provider="Amazon Bedrock", name="mistral.mistral-7b-instruct-v0:2", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="mistral.mixtral-8x7b-instruct-v0:1", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="mistral.mistral-large-2402-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="mistral.mistral-large-2407-v1:0", icon="Amazon", tool_calling=True
    ),
    create_model_metadata(
        provider="Amazon Bedrock", name="mistral.mistral-small-2402-v1:0", icon="Amazon", tool_calling=True
    ),
]

# Generate backwards-compatible list from the metadata
AWS_MODEL_IDs = [metadata["name"] for metadata in AWS_MODELS_DETAILED]

AWS_EMBEDDING_MODEL_IDS = [
    # Amazon Titan Embedding Models
    "amazon.titan-embed-text-v1",
    "amazon.titan-embed-text-v2:0",
    # Cohere Embedding Models
    "cohere.embed-english-v3",
    "cohere.embed-multilingual-v3",
]

AWS_REGIONS = [
    "us-west-2",
    "us-west-1",
    "us-gov-west-1",
    "us-gov-east-1",
    "us-east-2",
    "us-east-1",
    "sa-east-1",
    "me-south-1",
    "me-central-1",
    "il-central-1",
    "eu-west-3",
    "eu-west-2",
    "eu-west-1",
    "eu-south-2",
    "eu-south-1",
    "eu-north-1",
    "eu-central-2",
    "eu-central-1",
    "cn-northwest-1",
    "cn-north-1",
    "ca-west-1",
    "ca-central-1",
    "ap-southeast-5",
    "ap-southeast-4",
    "ap-southeast-3",
    "ap-southeast-2",
    "ap-southeast-1",
    "ap-south-2",
    "ap-south-1",
    "ap-northeast-3",
    "ap-northeast-2",
    "ap-northeast-1",
    "ap-east-1",
    "af-south-1",
]
