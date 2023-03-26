from langflow.node.nodes import ZeroShotPromptNode


def get_custom_prompts():
    """Get custom prompts."""
    return ZeroShotPromptNode().to_dict()
