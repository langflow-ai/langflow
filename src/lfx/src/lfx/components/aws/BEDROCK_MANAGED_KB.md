# Bedrock Managed Knowledge Base Support

## Overview
Adds a Langflow component that queries Amazon Bedrock Knowledge Bases for managed retrieval in visual workflows.

## Usage
```python
from lfx.components.aws.bedrock_kb import BedrockKnowledgeBaseComponent

component = BedrockKnowledgeBaseComponent()
component.set(
    knowledge_base_id="YOUR_KB_ID",
    region="us-east-1",
    use_agentic_retrieval=True,
)
results = component.retrieve("What are our data retention policies?")
```

In Langflow UI: drag the **Bedrock Knowledge Base** component onto the canvas and configure via the properties panel.

## Configuration
| Variable | Description | Default |
|---|---|---|
| KNOWLEDGE_BASE_ID | Bedrock Knowledge Base ID | None |
| AWS_REGION | AWS region for the KB | us-east-1 |
| AWS_PROFILE | AWS credentials profile | None |
| USE_AGENTIC_RETRIEVAL | Enable agentic retrieval | true |
| MAX_RESULTS | Maximum retrieval results | 5 |

## Features
- Managed search (no vector store needed)
- Agentic retrieval with query decomposition + reranking
- Automatic fallback to plain Retrieve if agentic fails
- Multi-source support (S3, Web, Confluence, SharePoint)
- Visual configuration in Langflow canvas

## SDK Requirements
- boto3 >= 1.43
- langflow >= 1.0

## Reranking Options
For managed search, these reranking modes are available:
- `MANAGED` (default) — automatic reranking by Bedrock
- `NONE` — disable reranking
- `CUSTOM` — your own Bedrock reranking model (e.g., Cohere Rerank v3.5)

## References
- [Build a Managed Knowledge Base](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-build-managed.html)
- [Retrieve API](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-retrieve.html)
- [Agentic Retrieval](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-agentic.html)

## Required IAM Permissions
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:Retrieve",
    "bedrock:AgenticRetrieveStream"
  ],
  "Resource": "arn:aws:bedrock:<region>:<account-id>:knowledge-base/<kb-id>"
}
```
