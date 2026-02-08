from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.policies.policies_component import (
    BUILD_MODE_CACHE,
    BUILD_MODE_GENERATE,
    STEP2,
    PoliciesComponent,
)


@pytest.fixture
def mock_tool():
    """Create a mock tool for testing."""
    tool = MagicMock()
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.tags = []
    tool.metadata = {}
    return tool


@pytest.fixture
def mock_component(mock_tool):
    """Create a PoliciesComponent instance with mocked dependencies."""
    with patch.object(PoliciesComponent, "user_id", new_callable=lambda: property(lambda _: "test_user_123")):
        component = PoliciesComponent()
        component.project = "test_project"
        component.in_tools = [mock_tool]
        component.policies = ["Policy 1: Do not allow negative numbers", "Policy 2: Validate input"]
        component.model = [{"name": "gpt-5.1", "provider": "OpenAI"}]
        component.api_key = "test_api_key"  # pragma: allowlist secret
        component.active = True
        component.build_mode = BUILD_MODE_CACHE
        return component


@pytest.mark.asyncio
async def test_cache_mode_success(mock_component, mock_tool):
    """Test PoliciesComponent in cache mode with valid cached guards."""
    code_dir = mock_component.work_dir / STEP2

    # Mock the cache directory exists
    with (
        patch.object(Path, "exists", return_value=True),
        patch("lfx.components.policies.policies_component.load_toolguards") as mock_load,
        patch("lfx.components.policies.policies_component.GuardedTool") as mock_guarded_tool,
    ):
        mock_load.return_value = MagicMock()
        mock_guarded_instance = MagicMock()
        mock_guarded_tool.return_value = mock_guarded_instance

        result = await mock_component.guard_tools()

        # Verify load_toolguards was called with correct directory
        mock_load.assert_called_once_with(code_dir)

        # Verify GuardedTool was created for each tool
        assert mock_guarded_tool.call_count == len(mock_component.in_tools)
        mock_guarded_tool.assert_called_with(mock_tool, mock_component.in_tools, code_dir)

        # Verify result contains guarded tools
        assert len(result) == 1
        assert result[0] == mock_guarded_instance


@pytest.mark.asyncio
async def test_cache_mode_directory_not_found(mock_component):
    """Test PoliciesComponent in cache mode when cache directory doesn't exist."""
    # Mock the cache directory does not exist
    with (
        patch.object(Path, "exists", return_value=False),
        pytest.raises(ValueError, match="Cache directory not found"),
    ):
        await mock_component.guard_tools()


@pytest.mark.asyncio
async def test_cache_mode_file_not_found(mock_component):
    """Test PoliciesComponent in cache mode when required files are missing."""
    # Mock the cache directory exists but files are missing
    with (
        patch.object(Path, "exists", return_value=True),
        patch("lfx.components.policies.policies_component.load_toolguards") as mock_load,
    ):
        mock_load.side_effect = FileNotFoundError("Guard file not found")

        with pytest.raises(ValueError, match="Required guard code files missing"):
            await mock_component.guard_tools()


@pytest.mark.asyncio
async def test_cache_mode_corrupted_cache(mock_component):
    """Test PoliciesComponent in cache mode when cached code is corrupted."""
    # Mock the cache directory exists but code is corrupted
    with (
        patch.object(Path, "exists", return_value=True),
        patch("lfx.components.policies.policies_component.load_toolguards") as mock_load,
    ):
        mock_load.side_effect = Exception("Invalid Python syntax")

        with pytest.raises(ValueError, match="Failed to load guard code"):
            await mock_component.guard_tools()


@pytest.mark.asyncio
async def test_cache_mode_multiple_tools(mock_component):
    """Test PoliciesComponent in cache mode with multiple tools."""
    # Add more tools
    tool2 = MagicMock()
    tool2.name = "tool2"
    tool3 = MagicMock()
    tool3.name = "tool3"
    mock_component.in_tools = [mock_component.in_tools[0], tool2, tool3]

    with (
        patch.object(Path, "exists", return_value=True),
        patch("lfx.components.policies.policies_component.load_toolguards") as mock_load,
        patch("lfx.components.policies.policies_component.GuardedTool") as mock_guarded_tool,
    ):
        mock_load.return_value = MagicMock()
        mock_guarded_instances = [MagicMock(), MagicMock(), MagicMock()]
        mock_guarded_tool.side_effect = mock_guarded_instances

        result = await mock_component.guard_tools()

        # Verify GuardedTool was created for each tool
        assert mock_guarded_tool.call_count == 3
        assert len(result) == 3
        assert result == mock_guarded_instances


@pytest.mark.asyncio
async def test_inactive_returns_original_tools(mock_component, mock_tool):
    """Test PoliciesComponent when active=False returns original tools."""
    mock_component.active = False

    result = await mock_component.guard_tools()

    # Should return original tools without wrapping
    assert result == mock_component.in_tools
    assert len(result) == 1
    assert result[0] == mock_tool


@pytest.mark.asyncio
async def test_generate_mode_validation_errors(mock_component):
    """Test PoliciesComponent in generate mode with validation errors."""
    mock_component.build_mode = BUILD_MODE_GENERATE

    # Test empty project
    mock_component.project = ""
    with pytest.raises(ValueError, match="project cannot be empty"):
        await mock_component.guard_tools()

    # Test empty policies
    mock_component.project = "test_project"
    mock_component.policies = []
    with pytest.raises(ValueError, match="policies cannot be empty"):
        await mock_component.guard_tools()

    # Test empty tools
    mock_component.policies = ["Policy 1"]
    mock_component.in_tools = []
    with pytest.raises(ValueError, match="in_tools cannot be empty"):
        await mock_component.guard_tools()

    # Test missing model
    mock_component.in_tools = [MagicMock()]
    mock_component.model = None
    with pytest.raises(ValueError, match="model or api_key cannot be empty"):
        await mock_component.guard_tools()

    # Test non-recommended model
    mock_component.model = [{"name": "gpt-3.5-turbo", "provider": "OpenAI"}]
    mock_component.api_key = "test_key"  # pragma: allowlist secret
    with pytest.raises(ValueError, match="is not in recommended models"):
        await mock_component.guard_tools()


def test_work_dir_property():
    """Test work_dir property generates correct path."""
    with patch.object(PoliciesComponent, "user_id", new_callable=lambda: property(lambda _: "test_user_123")):
        component = PoliciesComponent()
        component.project = "test_project"
        work_dir = component.work_dir

        assert "test_user_123" in str(work_dir)
        assert "test_project" in str(work_dir)
        assert work_dir.name == "test_project"


def test_to_snake_case():
    """Test _to_snake_case static method."""
    assert PoliciesComponent._to_snake_case("My Project") == "my_project"
    assert PoliciesComponent._to_snake_case("Test-Project") == "test_project"
    assert PoliciesComponent._to_snake_case("User's Project") == "user_s_project"
    assert PoliciesComponent._to_snake_case("Project, Name") == "project__name"
    assert PoliciesComponent._to_snake_case("UPPERCASE") == "uppercase"
    assert PoliciesComponent._to_snake_case("Mixed-Case Project's Name") == "mixed_case_project_s_name"


def test_in_recommended_models(mock_component):
    """Test in_recommended_models method."""
    assert mock_component.in_recommended_models("gpt-5.1") is True
    assert mock_component.in_recommended_models("claude-sonnet-4") is True
    assert mock_component.in_recommended_models("gpt-5.1-turbo") is True
    assert mock_component.in_recommended_models("claude-sonnet-4-preview") is True
    assert mock_component.in_recommended_models("gpt-4") is False
    assert mock_component.in_recommended_models("gpt-3.5-turbo") is False
    assert mock_component.in_recommended_models("claude-3") is False


@pytest.mark.asyncio
async def test_verify_cached_guards_error_messages(mock_component):
    """Test that _verify_cached_guards provides helpful error messages."""
    code_dir = mock_component.work_dir / STEP2

    # Test directory not found error message
    with patch.object(Path, "exists", return_value=False):
        with pytest.raises(ValueError, match="Cache directory not found") as exc_info:
            mock_component._verify_cached_guards(code_dir)

        assert "Generate" in str(exc_info.value)
        assert str(code_dir) in str(exc_info.value)

    # Test file not found error message
    with (
        patch.object(Path, "exists", return_value=True),
        patch("lfx.components.policies.policies_component.load_toolguards") as mock_load,
    ):
        mock_load.side_effect = FileNotFoundError("Missing file")

        with pytest.raises(ValueError, match="Required guard code files missing") as exc_info:
            mock_component._verify_cached_guards(code_dir)

        assert "Generate" in str(exc_info.value)

    # Test general error message
    with (
        patch.object(Path, "exists", return_value=True),
        patch("lfx.components.policies.policies_component.load_toolguards") as mock_load,
    ):
        mock_load.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(ValueError, match="Failed to load guard code") as exc_info:
            mock_component._verify_cached_guards(code_dir)

        assert "corrupted" in str(exc_info.value)
        assert "Unexpected error" in str(exc_info.value)


# Made with Bob
