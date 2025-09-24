"""
Example usage of DOCX processing components in Genesis Studio.

This script demonstrates how to use the processing components programmatically
or configure them in a Genesis Studio flow.
"""

import json
from typing import Any, Dict

# Example configuration for each component


def create_flow_configuration() -> Dict[str, Any]:
    """Create a complete flow configuration for DOCX processing."""

    flow_config = {
        "name": "DOCX Document Processing Pipeline",
        "description": "Extract structured blocks from DOCX documents",
        "components": [
            {
                "id": "blob_storage_1",
                "type": "Blob Storage",
                "config": {
                    "container_name": "documents",
                    "blob_name": "sample.docx",
                    "connection_string": "DefaultEndpointsProtocol=https;...",
                },
                "outputs": ["file_content"],
            },
            {
                "id": "docx_processor_1",
                "type": "DOCX Processor",
                "config": {"extract_images": True, "extract_sections": True},
                "inputs": {"file_input": "blob_storage_1.file_content"},
                "outputs": ["document"],
            },
            {
                "id": "text_extractor_1",
                "type": "Template Text Extractor",
                "config": {"include_metadata": True},
                "inputs": {"document_json": "docx_processor_1.document"},
                "outputs": ["extracted_text"],
            },
            {
                "id": "prompt_generator_1",
                "type": "Block Extraction Prompts",
                "config": {"extraction_mode": "llm", "include_examples": False},
                "inputs": {
                    "cleaned_lines": "text_extractor_1.extracted_text.cleaned_lines"
                },
                "outputs": ["combined_prompt"],
            },
            {
                "id": "azure_openai_1",
                "type": "Azure OpenAI",
                "config": {
                    "model": "gpt-4",
                    "temperature": 0,
                    "max_tokens": 16384,
                    "response_format": {"type": "json_object"},
                },
                "inputs": {"messages": "prompt_generator_1.combined_prompt.messages"},
                "outputs": ["response"],
            },
            {
                "id": "json_parser_1",
                "type": "Parse JSON",
                "inputs": {"text_input": "azure_openai_1.response"},
                "outputs": ["json_output"],
            },
            {
                "id": "block_mapper_1",
                "type": "Block Mapper",
                "config": {"file_name": "processed_document"},
                "inputs": {
                    "text_data": "text_extractor_1.extracted_text",
                    "llm_response": "json_parser_1.json_output",
                    "document_json": "docx_processor_1.document",
                },
                "outputs": ["mapped_blocks", "section_blocks", "statistics"],
            },
        ],
        "connections": [
            {
                "from": "blob_storage_1.file_content",
                "to": "docx_processor_1.file_input",
            },
            {
                "from": "docx_processor_1.document",
                "to": "text_extractor_1.document_json",
            },
            {
                "from": "text_extractor_1.extracted_text",
                "to": "prompt_generator_1.cleaned_lines",
            },
            {
                "from": "prompt_generator_1.combined_prompt",
                "to": "azure_openai_1.messages",
            },
            {"from": "azure_openai_1.response", "to": "json_parser_1.text_input"},
            {
                "from": "text_extractor_1.extracted_text",
                "to": "block_mapper_1.text_data",
            },
            {"from": "json_parser_1.json_output", "to": "block_mapper_1.llm_response"},
            {"from": "docx_processor_1.document", "to": "block_mapper_1.document_json"},
        ],
    }

    return flow_config


def create_bert_flow_configuration() -> Dict[str, Any]:
    """Create a flow configuration using BERT instead of LLM."""

    flow_config = {
        "name": "DOCX Processing with BERT",
        "description": "Extract blocks using BERT model",
        "components": [
            # ... (similar to above but with BERT configuration)
            {
                "id": "prompt_generator_1",
                "type": "Block Extraction Prompts",
                "config": {
                    "extraction_mode": "bert",  # Changed to BERT
                    "include_examples": False,
                },
                "outputs": ["bert_request"],
            },
            {
                "id": "api_request_1",
                "type": "API Request",
                "config": {
                    "url": "https://your-bert-endpoint/predict",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                },
                "inputs": {"body": "prompt_generator_1.bert_request"},
                "outputs": ["response"],
            },
            # ... rest of the flow
        ],
    }

    return flow_config


def example_component_outputs():
    """Show example outputs from each component."""

    # Example DOCX Processor output
    docx_output = {
        "body": {
            "type": "body",
            "content": [
                {
                    "type": "Paragraph",
                    "element_id": "abc123",
                    "content": [
                        {
                            "type": "Run",
                            "content": [
                                {"type": "Text", "value": "AUTONOMIZE HEALTH PLAN"}
                            ],
                        }
                    ],
                }
            ],
        },
        "images": {},
        "sections": [],
        "element_ids": ["abc123", "def456"],
        "metadata": {
            "processor": "DocxProcessor",
            "version": "1.0",
            "elements_count": 2,
        },
    }

    # Example Template Text Extractor output
    text_extractor_output = {
        "cleaned_lines": {
            "Paragraph 1": {"element_id": "abc123", "text": "AUTONOMIZE HEALTH PLAN"},
            "Paragraph 2": {"element_id": "def456", "text": "123 Main Street"},
        },
        "ordered_ids": ["abc123", "def456"],
        "metadata": {"total_elements": 2, "text_elements": 2},
    }

    # Example LLM response (parsed)
    llm_response = {
        "Company Name": {"element_ids": ["abc123"]},
        "Address": {"element_ids": ["def456"]},
    }

    # Example Block Mapper output
    block_mapper_output = {
        "name": "processed_document",
        "blocks": [
            {
                "name": "Company Name",
                "type": "processed",
                "content": [
                    {
                        "element_id": "abc123",
                        "type": "text",
                        "content": "AUTONOMIZE HEALTH PLAN",
                    }
                ],
            },
            {
                "name": "Address",
                "type": "processed",
                "content": [
                    {
                        "element_id": "def456",
                        "type": "text",
                        "content": "123 Main Street",
                    }
                ],
            },
        ],
        "statistics": {
            "total_elements": 2,
            "processed_blocks": 2,
            "structural_elements": 0,
            "empty_elements": 0,
            "unknown_elements": 0,
        },
    }

    return {
        "docx_processor": docx_output,
        "text_extractor": text_extractor_output,
        "llm_response": llm_response,
        "block_mapper": block_mapper_output,
    }


def create_agent_invocation_example():
    """Example of using components in agent/tool mode."""

    agent_config = {
        "agent_prompt": """
        Process the uploaded DOCX document through the following steps:
        1. Extract content using DOCX Processor
        2. Extract text elements using Template Text Extractor
        3. Generate block extraction prompts
        4. Call Azure OpenAI to identify blocks
        5. Map the blocks using Block Mapper

        Return the final structured blocks with statistics.
        """,
        "tools": [
            "DOCX Processor",
            "Template Text Extractor",
            "Block Extraction Prompts",
            "Block Mapper",
        ],
        "llm_config": {"provider": "azure_openai", "model": "gpt-4", "temperature": 0},
    }

    return agent_config


if __name__ == "__main__":
    # Create and print flow configuration
    flow = create_flow_configuration()
    print("Flow Configuration:")
    print(json.dumps(flow, indent=2))

    print("\n" + "=" * 50 + "\n")

    # Show example outputs
    examples = example_component_outputs()
    print("Example Component Outputs:")
    for component, output in examples.items():
        print(f"\n{component}:")
        print(json.dumps(output, indent=2)[:500] + "...")

    print("\n" + "=" * 50 + "\n")

    # Show agent configuration
    agent = create_agent_invocation_example()
    print("Agent Configuration:")
    print(json.dumps(agent, indent=2))
