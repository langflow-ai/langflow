from langflow.template import frontend_node

# These should always be instantiated
CUSTOM_NODES = {
    "prompts": {"ZeroShotPrompt": frontend_node.prompts.ZeroShotPromptNode()},
    "tools": {
        "PythonFunctionTool": frontend_node.tools.PythonFunctionToolNode(),
        "Tool": frontend_node.tools.ToolNode(),
    },
    "agents": {
        "JsonAgent": frontend_node.agents.JsonAgentNode(),
        "CSVAgent": frontend_node.agents.CSVAgentNode(),
        "initialize_agent": frontend_node.agents.InitializeAgentNode(),
        "VectorStoreAgent": frontend_node.agents.VectorStoreAgentNode(),
        "VectorStoreRouterAgent": frontend_node.agents.VectorStoreRouterAgentNode(),
        "SQLAgent": frontend_node.agents.SQLAgentNode(),
    },
    "utilities": {
        "SQLDatabase": frontend_node.agents.SQLDatabaseNode(),
    },
    "chains": {
        "SeriesCharacterChain": frontend_node.chains.SeriesCharacterChainNode(),
        "TimeTravelGuideChain": frontend_node.chains.TimeTravelGuideChainNode(),
        "MidJourneyPromptChain": frontend_node.chains.MidJourneyPromptChainNode(),
    },
}


def get_custom_nodes(node_type: str):
    """Get custom nodes."""
    return CUSTOM_NODES.get(node_type, {})
