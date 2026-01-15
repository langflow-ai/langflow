"""Flow execution service."""

import json
from pathlib import Path

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.run.base import run_flow

# Base path for flow JSON files
FLOWS_BASE_PATH = Path(__file__).parent.parent / "flows"

# Provider to LangChain model class mapping
MODEL_CLASS_MAP: dict[str, str] = {
    "OpenAI": "ChatOpenAI",
    "Anthropic": "ChatAnthropic",
    "Google Generative AI": "ChatGoogleGenerativeAI",
    "Groq": "ChatGroq",
    "Ollama": "ChatOllama",
}


def inject_model_into_flow(
    flow_data: dict,
    provider: str,
    model_name: str,
    api_key_var: str,
) -> dict:
    """Inject model configuration into the flow's Agent component.

    Args:
        flow_data: The flow JSON as a dict
        provider: The provider name (e.g., "OpenAI", "Anthropic")
        model_name: The model name (e.g., "gpt-4o", "claude-sonnet-4-5-20250929")
        api_key_var: The API key variable name (e.g., "OPENAI_API_KEY")

    Returns:
        Modified flow data with the model configuration injected
    """
    model_class = MODEL_CLASS_MAP.get(provider, "ChatOpenAI")

    model_value = [{
        "category": provider,
        "icon": provider.replace(" ", ""),
        "metadata": {
            "api_key_param": "api_key",
            "context_length": 128000,
            "model_class": model_class,
            "model_name_param": "model",
        },
        "name": model_name,
        "provider": provider,
    }]

    for node in flow_data.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        if node_data.get("type") == "Agent":
            template = node_data.get("node", {}).get("template", {})
            if "model" in template:
                template["model"]["value"] = model_value
            if "api_key" in template:
                template["api_key"]["value"] = api_key_var
            break

    return flow_data


async def execute_flow_file(
    flow_filename: str,
    input_value: str | None = None,
    global_variables: dict[str, str] | None = None,
    *,
    verbose: bool = False,
    user_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> dict:
    """Execute a flow from a JSON file.

    Args:
        flow_filename: Name of the flow file (e.g., "MyFlow.json")
        input_value: Input value to pass to the flow
        global_variables: Dict of global variables to inject into the flow context
        verbose: Whether to enable verbose logging
        user_id: User ID for components that require user context
        provider: Model provider to inject into Agent nodes
        model_name: Model name to inject into Agent nodes
        api_key_var: API key variable name to inject into Agent nodes

    Returns:
        dict: Result from flow execution

    Raises:
        HTTPException: If flow file not found or execution fails
    """
    flow_path = FLOWS_BASE_PATH / flow_filename

    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow file '{flow_filename}' not found")

    try:
        flow_data = json.loads(flow_path.read_text())

        if provider and model_name and api_key_var:
            flow_data = inject_model_into_flow(flow_data, provider, model_name, api_key_var)

        flow_json = json.dumps(flow_data)
        result = await run_flow(
            flow_json=flow_json,
            input_value=input_value,
            global_variables=global_variables or {},
            verbose=verbose,
            check_variables=False,
            user_id=user_id,
        )
    except Exception as e:
        logger.error(f"Flow execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing flow: {e}") from e

    return result


def extract_response_text(result: dict) -> str:
    """Extract text from flow execution result."""
    if "result" in result:
        return result["result"]
    if "text" in result:
        return result["text"]
    if "exception_message" in result:
        return result["exception_message"]

    return str(result)
