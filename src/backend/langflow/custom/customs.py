from langflow.template.frontend_node import nodes

# These should always be instantiated
CUSTOM_NODES = {
    "prompts": {"ZeroShotPrompt": nodes.ZeroShotPromptNode()},
    "tools": {"PythonFunction": nodes.PythonFunctionNode(), "Tool": nodes.ToolNode()},
    "agents": {
        "JsonAgent": nodes.JsonAgentNode(),
        "CSVAgent": nodes.CSVAgentNode(),
        "initialize_agent": nodes.InitializeAgentNode(),
        "VectorStoreAgent": nodes.VectorStoreAgentNode(),
        "VectorStoreRouterAgent": nodes.VectorStoreRouterAgentNode(),
        "SQLAgent": nodes.SQLAgentNode(),
    },
    "utilities": {
        "SQLDatabase": nodes.SQLDatabaseNode(),
    },
    "chains": {
        "SeriesCharacterChain": nodes.SeriesCharacterChainNode(),
        "TimeTravelGuideChain": nodes.TimeTravelGuideChainNode(),
        "MidJourneyPromptChain": nodes.MidJourneyPromptChainNode(),
    },
    "connectors": {
        "ConnectorFunction": nodes.ConnectorFunctionFrontendNode(),
        "DallE2Generator": nodes.DallE2GeneratorFrontendNode(),
    },
}


def get_custom_nodes(node_type: str):
    """Get custom nodes."""
    return CUSTOM_NODES.get(node_type, {})
