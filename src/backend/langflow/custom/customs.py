from langflow.template import frontend_node

# These should always be instantiated
CUSTOM_NODES = {
    # "prompts": {
    #     "ZeroShotPrompt": frontend_node.prompts.ZeroShotPromptNode(),
    # },
    "tools": {
        "PythonFunctionTool": frontend_node.PythonFunctionToolNode(),
        "Tool": frontend_node.ToolNode(),
    },
    "agents": {
        "JsonAgent": frontend_node.JsonAgentNode(),
        "CSVAgent": frontend_node.CSVAgentNode(),
        "AgentInitializer": frontend_node.InitializeAgentNode(),
        "VectorStoreAgent": frontend_node.VectorStoreAgentNode(),
        "VectorStoreRouterAgent": frontend_node.VectorStoreRouterAgentNode(),
        "SQLAgent": frontend_node.SQLAgentNode(),
    },
    "utilities": {
        "SQLDatabase": frontend_node.SQLDatabaseNode(),
    },
    "memories": {
        "PostgresChatMessageHistory": frontend_node.memories.PostgresChatMessageHistoryFrontendNode(),
        "MongoDBChatMessageHistory": frontend_node.memories.MongoDBChatMessageHistoryFrontendNode(),
    },
    "chains": {
        "SeriesCharacterChain": frontend_node.SeriesCharacterChainNode(),
        "TimeTravelGuideChain": frontend_node.TimeTravelGuideChainNode(),
        "MidJourneyPromptChain": frontend_node.MidJourneyPromptChainNode(),
        "load_qa_chain": frontend_node.CombineDocsChainNode(),
    },
    "connectors": {
        "ConnectorFunction": frontend_node.ConnectorFunctionFrontendNode(),
        "DallE2Generator": frontend_node.DallE2GeneratorFrontendNode(),
    },
}


def get_custom_nodes(node_type: str):
    """Get custom nodes."""
    return CUSTOM_NODES.get(node_type, {})
