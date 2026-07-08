from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.models_and_agents.policies_component import (
    MODE_GENERATE,
    MODE_GUARD,
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
        component.enabled = True
        component.mode = MODE_GUARD
        return component


def _make_fake_tg(**overrides):
    """Build a fake toolguard-imports dict for use with `_import_toolguard` patching.

    Mirrors the keys returned by `PoliciesComponent._import_toolguard()`; tests
    can override individual entries to assert specific call wiring.
    """
    fake = {
        "PolicySpecOptions": MagicMock(),
        "ToolGuardsCodeGenerationResult": MagicMock(),
        "generate_guard_specs": MagicMock(),
        "generate_guards_code": MagicMock(),
        "langchain_tools_to_openapi": MagicMock(),
        "load_toolguards": MagicMock(),
        "load_toolguards_from_memory": MagicMock(),
        "RESULTS_FILENAME": "results.json",
        "sync_generated_guard_code_inputs": MagicMock(),
        "GuardedTool": MagicMock(),
        "LangchainModelWrapper": MagicMock(),
    }
    fake.update(overrides)
    return fake


@pytest.mark.asyncio
async def test_guard_tools_blocked_when_custom_components_disabled(mock_component, monkeypatch):
    """ToolGuard guard execution must be refused under allow_custom_components=False.

    Regression test: the guard code comes from client-editable CodeInput
    template values that bypass the custom-component hash gate, so a locked-down
    deployment must refuse to execute it. The refusal happens before any toolguard
    import/exec.
    """
    from types import SimpleNamespace

    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=False)),
    )

    # The refusal must happen before any toolguard runtime is imported/exec'd.
    with (
        patch.object(PoliciesComponent, "_import_toolguard") as mock_import,
        pytest.raises(ValueError, match="allow_custom_components"),
    ):
        await mock_component.guard_tools()
    mock_import.assert_not_called()


@pytest.mark.asyncio
async def test_guard_tools_allowed_when_custom_components_enabled(mock_component, monkeypatch):
    """ToolGuard guard execution must reach the runtime when allow_custom_components=True.

    Pins the allow side of the gate: with the flag enabled, guard_tools() must get
    past _code_execution_allowed() and import the toolguard runtime. Without this,
    a future flip of the default would silently bypass the security gate and only
    the blocked path would be covered.
    """
    from types import SimpleNamespace

    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True)),
    )

    fake_tg = _make_fake_tg()
    fake_tg["load_toolguards_from_memory"].return_value = MagicMock()
    fake_tg["GuardedTool"].return_value = MagicMock()

    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg) as mock_import,
        patch.object(mock_component, "make_toolguard_result", return_value=MagicMock()),
    ):
        await mock_component.guard_tools()

    mock_import.assert_called()


async def test_cache_mode_success(mock_component, mock_tool):
    """Test PoliciesComponent in cache mode with valid cached guards."""
    code_dir = mock_component.work_dir / STEP2

    fake_tg = _make_fake_tg()
    mock_tg_result = MagicMock()
    mock_tg_runtime = MagicMock()
    fake_tg["load_toolguards_from_memory"].return_value = mock_tg_runtime
    mock_guarded_instance = MagicMock()
    fake_tg["GuardedTool"].return_value = mock_guarded_instance

    # Mock the cache directory exists and toolguard loading
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg),
        patch.object(mock_component, "make_toolguard_result") as mock_make_result,
    ):
        mock_make_result.return_value = mock_tg_result

        result = await mock_component.guard_tools()

        # Verify load_toolguards was called during validation
        fake_tg["load_toolguards"].assert_called_once_with(code_dir)

        # Verify make_toolguard_result was called
        mock_make_result.assert_called_once()

        # Verify load_toolguards_from_memory was called with the result
        fake_tg["load_toolguards_from_memory"].assert_called_once_with(mock_tg_result)

        # Verify GuardedTool was created for each tool
        assert fake_tg["GuardedTool"].call_count == len(mock_component.in_tools)
        fake_tg["GuardedTool"].assert_called_with(mock_tool, mock_component.in_tools, mock_tg_runtime)

        # Verify result contains guarded tools
        assert len(result) == 1
        assert result[0] == mock_guarded_instance


@pytest.mark.asyncio
async def test_cache_mode_directory_not_found(mock_component):
    """Test PoliciesComponent in cache mode when cache directory doesn't exist."""
    fake_tg = _make_fake_tg()
    # Mock the cache directory does not exist
    with (
        patch.object(Path, "exists", return_value=False),
        patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg),
        pytest.raises(ValueError, match="Cache directory not found"),
    ):
        await mock_component.guard_tools()


@pytest.mark.asyncio
async def test_cache_mode_file_not_found(mock_component):
    """Test PoliciesComponent in cache mode when required files are missing."""
    fake_tg = _make_fake_tg()
    fake_tg["load_toolguards"].side_effect = FileNotFoundError("Guard file not found")
    # Mock the cache directory exists but files are missing
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg),
        pytest.raises(ValueError, match="Required guard code files missing"),
    ):
        await mock_component.guard_tools()


@pytest.mark.asyncio
async def test_cache_mode_corrupted_cache(mock_component):
    """Test PoliciesComponent in cache mode when cached code is corrupted."""
    fake_tg = _make_fake_tg()
    fake_tg["load_toolguards"].side_effect = Exception("Invalid Python syntax")
    # Mock the cache directory exists but code is corrupted
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg),
        pytest.raises(ValueError, match="Failed to load guard code"),
    ):
        await mock_component.guard_tools()


# @pytest.mark.asyncio
# async def test_cache_mode_multiple_tools(mock_component):
#     """Test PoliciesComponent in cache mode with multiple tools."""
#     # Add more tools
#     tool2 = MagicMock()
#     tool2.name = "tool2"
#     tool3 = MagicMock()
#     tool3.name = "tool3"
#     mock_component.in_tools = [mock_component.in_tools[0], tool2, tool3]

#     with (
#         patch.object(Path, "exists", return_value=True),
#         patch.object(mock_component, "make_toolguard_result") as mock_make_result,
#         patch("lfx.components.models_and_agents.policies_component.load_toolguards_from_memory") as mock_load_memory,
#         patch("lfx.components.models_and_agents.policies_component.GuardedTool") as mock_guarded_tool,
#     ):
#         mock_tg_result = MagicMock()
#         mock_make_result.return_value = mock_tg_result
#         mock_tg_runtime = MagicMock()
#         mock_load_memory.return_value = mock_tg_runtime
#         mock_guarded_instances = [MagicMock(), MagicMock(), MagicMock()]
#         mock_guarded_tool.side_effect = mock_guarded_instances

#         result = await mock_component.guard_tools()

#         # Verify GuardedTool was created for each tool
#         assert mock_guarded_tool.call_count == 3
#         assert len(result) == 3
#         assert result == mock_guarded_instances


@pytest.mark.asyncio
async def test_inenabled_returns_original_tools(mock_component, mock_tool):
    """Test PoliciesComponent when enabled=False returns original tools."""
    mock_component.enabled = False

    result = await mock_component.guard_tools()

    # Should return original tools without wrapping
    assert result == mock_component.in_tools
    assert len(result) == 1
    assert result[0] == mock_tool


@pytest.mark.asyncio
async def test_generate_mode_validation_errors(mock_component):
    """Test PoliciesComponent in generate mode with validation errors."""
    mock_component.mode = MODE_GENERATE
    fake_tg = _make_fake_tg()

    with patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg):
        # Test empty project
        mock_component.project = ""
        with pytest.raises(ValueError):  # noqa: PT011
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
        with pytest.raises(ValueError, match="model cannot be empty"):
            await mock_component.guard_tools()

    # # Test non-recommended model
    # mock_component.model = [{"name": "gpt-3.5-turbo", "provider": "OpenAI"}]
    # mock_component.api_key = "test_key"  # pragma: allowlist secret
    # with pytest.raises(ValueError, match="is not in recommended models"):
    #     await mock_component.guard_tools()


def test_work_dir_property():
    """Test work_dir property generates correct path."""
    component = PoliciesComponent()
    component.project = "test project"
    work_dir = component.work_dir

    assert "test_project" in str(work_dir)
    assert work_dir.name == "test_project"


def test_to_snake_case():
    """Test _to_snake_case static method."""
    assert PoliciesComponent._to_snake_case("My Project") == "my_project"
    assert PoliciesComponent._to_snake_case("Test-Project") == "test_project"
    assert PoliciesComponent._to_snake_case("User's Project") == "user_s_project"
    assert PoliciesComponent._to_snake_case("Project, Name") == "project_name"
    assert PoliciesComponent._to_snake_case("UPPERCASE") == "uppercase"
    assert PoliciesComponent._to_snake_case("Mixed-Case Project's Name") == "mixed_case_project_s_name"

    # Test path traversal prevention
    assert PoliciesComponent._to_snake_case("../../etc/passwd") == "etc_passwd"
    assert PoliciesComponent._to_snake_case("../../../root") == "root"
    assert PoliciesComponent._to_snake_case("./hidden") == "hidden"
    assert PoliciesComponent._to_snake_case("path/to/file") == "path_to_file"
    assert PoliciesComponent._to_snake_case("back\\slash\\path") == "back_slash_path"

    # Test special characters are sanitized
    assert PoliciesComponent._to_snake_case("test@#$%project") == "test_project"
    assert PoliciesComponent._to_snake_case("___multiple___underscores___") == "multiple_underscores"

    # Test empty/invalid input
    with pytest.raises(ValueError, match="must contain at least one alphanumeric character"):
        PoliciesComponent._to_snake_case("...")
    with pytest.raises(ValueError, match="must contain at least one alphanumeric character"):
        PoliciesComponent._to_snake_case("___")
    with pytest.raises(ValueError, match="must contain at least one alphanumeric character"):
        PoliciesComponent._to_snake_case("@#$%")


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
    fake_tg = _make_fake_tg()
    with (
        patch.object(Path, "exists", return_value=False),
        patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg),
    ):
        with pytest.raises(ValueError, match="Cache directory not found") as exc_info:
            mock_component._verify_cached_guards(code_dir)

        assert "Generate" in str(exc_info.value)
        assert str(code_dir) in str(exc_info.value)

    # Test file not found error message
    fake_tg = _make_fake_tg()
    fake_tg["load_toolguards"].side_effect = FileNotFoundError("Missing file")
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg),
    ):
        with pytest.raises(ValueError, match="Required guard code files missing") as exc_info:
            mock_component._verify_cached_guards(code_dir)

        assert "Generate" in str(exc_info.value)

    # Test general error message
    fake_tg = _make_fake_tg()
    fake_tg["load_toolguards"].side_effect = RuntimeError("Unexpected error")
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg),
    ):
        with pytest.raises(ValueError, match="Failed to load guard code") as exc_info:
            mock_component._verify_cached_guards(code_dir)

        assert "corrupted" in str(exc_info.value)
        assert "Unexpected error" in str(exc_info.value)


def test_template_field_key_normalizes_separators():
    """Node-template keys are POSIX; OS-separator file names must normalize to match.

    Regression for #13727: on Windows the toolguard result stores ``file_name`` as
    a Path whose ``str()`` uses backslashes, while ``sync_generated_guard_code_inputs``
    keys the template by ``Path.as_posix()`` (forward slashes). The lookup must
    normalize so it matches on every platform.
    """
    # Forward-slash input is unchanged.
    assert PoliciesComponent._template_field_key("proj/fetch_content/guard.py") == "proj/fetch_content/guard.py"
    # Backslash input (what str(WindowsPath(...)) yields) normalizes to forward slashes.
    assert PoliciesComponent._template_field_key("proj\\fetch_content\\guard.py") == "proj/fetch_content/guard.py"
    # Path inputs normalize too.
    assert PoliciesComponent._template_field_key(Path("proj/fetch_content/guard.py")) == "proj/fetch_content/guard.py"
    # Single-segment names (e.g. result.json) are unaffected.
    assert PoliciesComponent._template_field_key("result.json") == "result.json"


def _fake_file_twin(file_name):
    """A stand-in for toolguard's FileTwin: a ``file_name`` plus assignable ``content``."""
    from types import SimpleNamespace

    return SimpleNamespace(file_name=file_name, content=None)


def test_make_toolguard_result_reads_posix_keyed_fields(mock_component):
    """make_toolguard_result must read fields the sync step keyed by POSIX path.

    Regression for #13727 (the 'NoneType' object is not subscriptable crash on
    Windows). The toolguard result hands back ``file_name`` values using OS
    separators (here simulated with backslashes, exactly as ``str(WindowsPath)``
    produces), while the node template is keyed by forward-slash POSIX paths. The
    read path must normalize and match instead of returning ``None``.
    """
    from types import SimpleNamespace

    # file_name values as they arrive from the result model on Windows (backslashes).
    types_fn = "proj\\proj_types.py"
    api_fn = "proj\\proj_api.py"
    impl_fn = "proj\\proj_api_impl.py"
    guard_fn = "proj\\fetch_content\\guard.py"
    item_fn = "proj\\fetch_content\\guard_allowed_url_domains.py"

    fake_result = SimpleNamespace(
        domain=SimpleNamespace(
            app_types=_fake_file_twin(types_fn),
            app_api=_fake_file_twin(api_fn),
            app_api_impl=_fake_file_twin(impl_fn),
        ),
        tools={
            "fetch_content": SimpleNamespace(
                guard_file=_fake_file_twin(guard_fn),
                item_guard_files=[_fake_file_twin(item_fn)],
            )
        },
    )

    # Template keyed by POSIX paths, exactly as sync_generated_guard_code_inputs writes them.
    attrs = {
        "result.json": {"value": "{}"},
        "proj/proj_types.py": {"value": "types-content"},
        "proj/proj_api.py": {"value": "api-content"},
        "proj/proj_api_impl.py": {"value": "impl-content"},
        "proj/fetch_content/guard.py": {"value": "guard-content"},
        "proj/fetch_content/guard_allowed_url_domains.py": {"value": "item-content"},
    }

    fake_tg = _make_fake_tg(RESULTS_FILENAME="result.json")
    fake_tg["ToolGuardsCodeGenerationResult"].model_validate_json.return_value = fake_result

    mock_component.get_vertex = MagicMock(return_value=SimpleNamespace(data={"node": {"template": attrs}}))

    with patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg):
        result = mock_component.make_toolguard_result()

    assert result is fake_result
    assert result.domain.app_types.content == "types-content"
    assert result.domain.app_api.content == "api-content"
    assert result.domain.app_api_impl.content == "impl-content"
    assert result.tools["fetch_content"].guard_file.content == "guard-content"
    assert result.tools["fetch_content"].item_guard_files[0].content == "item-content"


def test_make_toolguard_result_missing_field_raises_clear_error(mock_component):
    """A missing generated field yields a clear ValueError, not a NoneType subscript.

    Before #13727's fix a missing key surfaced as
    ``'NoneType' object is not subscriptable``; it must now point the user at
    Generate mode instead.
    """
    from types import SimpleNamespace

    fake_result = SimpleNamespace(
        domain=SimpleNamespace(
            app_types=_fake_file_twin("proj/proj_types.py"),
            app_api=_fake_file_twin("proj/proj_api.py"),
            app_api_impl=_fake_file_twin("proj/proj_api_impl.py"),
        ),
        tools={},
    )

    # app_types key is intentionally absent from the template.
    attrs = {
        "result.json": {"value": "{}"},
        "proj/proj_api.py": {"value": "api-content"},
        "proj/proj_api_impl.py": {"value": "impl-content"},
    }

    fake_tg = _make_fake_tg(RESULTS_FILENAME="result.json")
    fake_tg["ToolGuardsCodeGenerationResult"].model_validate_json.return_value = fake_result

    mock_component.get_vertex = MagicMock(return_value=SimpleNamespace(data={"node": {"template": attrs}}))

    with (
        patch.object(PoliciesComponent, "_import_toolguard", return_value=fake_tg),
        pytest.raises(ValueError, match="missing from the component"),
    ):
        mock_component.make_toolguard_result()


def test_validate_before_generate_allows_empty_api_key(mock_component):
    """api_key is optional: validation passes when only the model is set.

    The field is declared required=False/advanced=True and credentials often come
    from the model connection or environment, so requiring api_key here wrongly
    blocked valid setups (the "model or api_key cannot be empty!" wart in #13727).
    """
    mock_component.api_key = ""
    mock_component.model = [{"name": "gpt-5.1", "provider": "OpenAI"}]
    # Should not raise.
    mock_component.validate_before_generate()


def test_validate_before_generate_still_requires_model(mock_component):
    """A missing model is still rejected after relaxing the api_key requirement."""
    mock_component.api_key = ""
    mock_component.model = None
    with pytest.raises(ValueError, match="model cannot be empty"):
        mock_component.validate_before_generate()


# Made with Bob
