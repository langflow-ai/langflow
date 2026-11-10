"""ALTK compatibility wrappers cannot silently bypass retired validation."""

import pytest
from lfx.base.agents.altk_base_agent import ALTKBaseTool, BaseToolWrapper, ToolPipelineManager
from lfx.base.agents.altk_tool_wrappers import (
    PostToolProcessingWrapper,
    PostToolProcessor,
    PreToolValidationWrapper,
    ValidatedTool,
)


@pytest.mark.parametrize(
    "wrapper_type",
    [
        ALTKBaseTool,
        BaseToolWrapper,
        PostToolProcessingWrapper,
        PostToolProcessor,
        PreToolValidationWrapper,
        ValidatedTool,
    ],
)
def test_retired_wrapper_construction_reports_migration(wrapper_type):
    with pytest.raises(RuntimeError, match=r"retired.*1\.13\.0"):
        wrapper_type()


def test_retired_pipeline_does_not_pass_through_tools():
    with pytest.raises(RuntimeError, match="retired"):
        ToolPipelineManager().process_tools([])


def test_retired_conversion_reports_migration():
    with pytest.raises(RuntimeError, match="retired"):
        PreToolValidationWrapper.convert_langchain_tools_to_sparc_tool_specs_format([])
