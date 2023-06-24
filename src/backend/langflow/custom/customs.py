from langflow.components import component

# These should always be instantiated
CUSTOM_NODES = {
    "prompts": {
        "ZeroShotPrompt": component.prompts.ZeroShotPromptNode(),
    },
    "tools": {
        "PythonFunctionTool": component.tools.PythonFunctionToolNode(),
        "PythonFunction": component.tools.PythonFunctionNode(),
        "Tool": component.tools.ToolNode(),
    },
    "agents": {
        "JsonAgent": component.agents.JsonAgentNode(),
        "CSVAgent": component.agents.CSVAgentNode(),
        "AgentInitializer": component.agents.InitializeAgentNode(),
        "VectorStoreAgent": component.agents.VectorStoreAgentNode(),
        "VectorStoreRouterAgent": component.agents.VectorStoreRouterAgentNode(),
        "SQLAgent": component.agents.SQLAgentNode(),
    },
    "utilities": {
        "SQLDatabase": component.agents.SQLDatabaseNode(),
    },
    "chains": {
        "SeriesCharacterChain": component.chains.SeriesCharacterChainNode(),
        "TimeTravelGuideChain": component.chains.TimeTravelGuideChainNode(),
        "MidJourneyPromptChain": component.chains.MidJourneyPromptChainNode(),
        "load_qa_chain": component.chains.CombineDocsChainNode(),
    },
    "io": {
        "Chat": component.io.ChatComponent(),
        "Form": component.io.FormComponent(),
    },
}


def get_custom_nodes(node_type: str) -> dict:
    """Get custom nodes."""
    return CUSTOM_NODES.get(node_type, {})
