"""Output name to method name mappings for code generation.

Maps (component_type, output_name) to the actual method name.
The JSON stores output names in sourceHandle.name, but the Python code needs
to call the method name for .set() connections to work correctly.
"""

from __future__ import annotations

OUTPUT_TO_METHOD: dict[str, str] = {
    # Input/Output
    "ChatInput.message": "message_response",
    "ChatOutput.message": "message_response",
    "TextInputComponent.text": "text_response",
    "TextOutputComponent.text": "text_response",
    # Models and Agents
    "AgentComponent.response": "message_response",
    "Agent.response": "message_response",
    "PromptComponent.prompt": "build_prompt",
    "Prompt.prompt": "build_prompt",
    "LanguageModelComponent.text_output": "text_response",
    "LanguageModel.text_output": "text_response",
    # OpenAI models inherit from LCModelComponent
    "OpenAIModel.text_output": "text_response",
    "OpenAIModelComponent.text_output": "text_response",
    "OpenAIModel.model_output": "build_model",
    "OpenAIModelComponent.model_output": "build_model",
    # All LCModelComponent subclasses
    "LCModelComponent.text_output": "text_response",
    "LCModelComponent.model_output": "build_model",
    "MemoryComponent.messages": "retrieve_messages",
    "Memory.messages": "retrieve_messages",
    # Data Sources
    "URLComponent.page_results": "fetch_content",
    "URLComponent.raw_results": "fetch_content_as_message",
    "WebSearchComponent.results": "search",
    "DirectoryComponent.dataframe": "as_dataframe",
    "FileComponent.data": "load_file",
    "APIRequest.data": "make_request",
    "AirtableComponent.data": "query_records",
    # Vector Stores
    "AstraDB.search_results": "search_documents",
    "AstraDBComponent.search_results": "search_documents",
    "ChromaComponent.search_results": "search_documents",
    "Chroma.search_results": "search_documents",
    "PineconeComponent.search_results": "search_documents",
    "Pinecone.search_results": "search_documents",
    "QdrantComponent.search_results": "search_documents",
    "Qdrant.search_results": "search_documents",
    "PGVectorComponent.search_results": "search_documents",
    "PGVector.search_results": "search_documents",
    "MilvusComponent.search_results": "search_documents",
    "Milvus.search_results": "search_documents",
    "WeaviateComponent.search_results": "search_documents",
    "Weaviate.search_results": "search_documents",
    "FAISSComponent.search_results": "search_documents",
    "FAISS.search_results": "search_documents",
    # Text Processing
    "SplitText.chunks": "split_text",
    "SplitTextComponent.chunks": "split_text",
    "ParseData.text": "parse_data",
    "ParseDataComponent.text": "parse_data",
    "CombineText.combined": "combine_text",
    "CombineTextComponent.combined": "combine_text",
    "FilterData.filtered": "filter_data",
    "FilterDataComponent.filtered": "filter_data",
    "ReplaceText.text": "replace_text",
    "ExtractKey.output": "extract_key",
    "MergeData.combined": "merge_data",
    "UpdateData.data": "update_data",
    "SelectivePassThrough.output": "select_output",
    "ConditionalRouter.output": "route_message",
    "ConditionalRouter.true_result": "true_response",
    "ConditionalRouter.false_result": "false_response",
    "ConditionalRouterComponent.true_result": "true_response",
    "ConditionalRouterComponent.false_result": "false_response",
    "Notify.output_value": "notify",
    "Listen.output_value": "listen",
    # Helpers
    "CalculatorComponent.result": "calculate",
    "Calculator.result": "calculate",
    "CurrentDateComponent.date": "get_current_date",
    "CurrentDate.date": "get_current_date",
    "IDGeneratorComponent.id": "generate_id",
    "IDGenerator.id": "generate_id",
    "CreateListComponent.list": "create_list",
    "CreateList.list": "create_list",
    "OutputParserComponent.output": "parse_output",
    "OutputParser.output": "parse_output",
}


def get_method_name(node_type: str, output_name: str) -> str:
    """Get the method name for a given component type and output name.

    Args:
        node_type: The component type (e.g., "ChatInput", "AgentComponent")
        output_name: The output name from JSON (e.g., "message", "response")

    Returns:
        The method name to use in generated code. Falls back to output_name
        if no mapping is found.
    """
    key = f"{node_type}.{output_name}"
    if key in OUTPUT_TO_METHOD:
        return OUTPUT_TO_METHOD[key]
    return output_name
