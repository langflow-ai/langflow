"""Import-compatible names for ALTK tool wrappers retired in Langflow 1.13.0."""

from lfx.base.agents.altk_base_agent import ALTKBaseTool, ALTKRetiredError, BaseToolWrapper


class ValidatedTool(ALTKBaseTool):
    """Historical validation wrapper. Construction reports retirement."""


class PostToolProcessor(ALTKBaseTool):
    """Historical output processor. Construction reports retirement."""


class PreToolValidationWrapper(BaseToolWrapper):
    """Historical SPARC wrapper. Construction reports retirement."""

    @staticmethod
    def convert_langchain_tools_to_sparc_tool_specs_format(tools):  # noqa: ARG004 - legacy interface
        """Reject validation-tool conversion through the retired ALTK integration."""
        raise ALTKRetiredError


class PostToolProcessingWrapper(BaseToolWrapper):
    """Historical output wrapper. Construction reports retirement."""
