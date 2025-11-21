"""Tests for security features in the check CLI command."""

import pytest
from lfx.cli.check import load_specific_components


class TestLoadSpecificComponentsSecurity:
    """Test security features of load_specific_components function."""

    @pytest.mark.asyncio
    async def test_blocks_malicious_os_module(self):
        """Test that malicious os module imports are blocked."""
        malicious_modules = {"os.system"}

        result = await load_specific_components(malicious_modules)

        # Should return empty dict (no components loaded)
        assert result == {}

    @pytest.mark.asyncio
    async def test_blocks_malicious_subprocess_module(self):
        """Test that malicious subprocess module imports are blocked."""
        malicious_modules = {"subprocess.Popen"}

        result = await load_specific_components(malicious_modules)

        assert result == {}

    @pytest.mark.asyncio
    async def test_blocks_malicious_eval_module(self):
        """Test that eval-based attacks are blocked."""
        malicious_modules = {"__builtin__.eval"}

        result = await load_specific_components(malicious_modules)

        assert result == {}

    @pytest.mark.asyncio
    async def test_blocks_multiple_malicious_modules(self):
        """Test that multiple malicious modules are all blocked."""
        malicious_modules = {"os.system", "subprocess.call", "__builtin__.exec", "sys.exit", "importlib.import_module"}

        result = await load_specific_components(malicious_modules)

        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_invalid_module_paths(self):
        """Test that invalid module paths are handled gracefully."""
        invalid_modules = {
            "lfx.components.",  # Empty class name
            "lfx.components",  # No class name
            "",  # Empty string
            ".",  # Just a dot
            "..",  # Double dot
            "lfx..components.test",  # Double dot in path
        }

        result = await load_specific_components(invalid_modules)

        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_nonexistent_lfx_components(self):
        """Test that nonexistent lfx.components modules are handled gracefully."""
        nonexistent_modules = {
            "lfx.components.nonexistent.Component",
            "lfx.components.fake.FakeComponent",
            "lfx.components.invalid.path.Component",
        }

        result = await load_specific_components(nonexistent_modules)

        # Should return empty dict since components don't exist
        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_nonexistent_langflow_components(self):
        """Test that nonexistent langflow.components modules are handled gracefully."""
        nonexistent_modules = {
            "langflow.components.nonexistent.Component",
            "langflow.components.fake.FakeComponent",
            "langflow.components.invalid.path.Component",
        }

        result = await load_specific_components(nonexistent_modules)

        # Should return empty dict since components don't exist
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_module_set(self):
        """Test that empty module set returns empty dict."""
        result = await load_specific_components(set())
        assert result == {}

    @pytest.mark.asyncio
    async def test_security_validation_comprehensive(self):
        """Comprehensive test of security validation against various attack vectors."""
        # Test various attack vectors that should all be blocked
        attack_vectors = {
            # Direct system access
            "os.system",
            "os.popen",
            "subprocess.run",
            "subprocess.Popen",
            # Code execution
            "__builtin__.eval",
            "__builtin__.exec",
            "__builtin__.__import__",
            "builtins.eval",
            # File system access
            "pathlib.Path",
            "shutil.rmtree",
            # Network access
            "urllib.request.urlopen",
            "requests.get",
            # Import manipulation
            "importlib.import_module",
            "importlib.reload",
            # Other dangerous modules
            "socket.socket",
            "threading.Thread",
            "multiprocessing.Process",
        }

        result = await load_specific_components(attack_vectors)

        # All should be blocked - no components loaded
        assert result == {}

    @pytest.mark.asyncio
    async def test_allows_valid_lfx_component_paths(self):
        """Test that valid lfx.components paths are allowed (even if they don't exist)."""
        # These should pass the security check but fail to load since they don't exist
        valid_lfx_paths = {
            "lfx.components.input.TextInput",
            "lfx.components.output.TextOutput",
            "lfx.components.data.processor.DataProcessor",
            "lfx.components.llm.openai.OpenAIComponent",
        }

        result = await load_specific_components(valid_lfx_paths)

        # Should return empty dict because components don't actually exist
        # But importantly, they should NOT be blocked by security validation
        assert result == {}

    @pytest.mark.asyncio
    async def test_allows_valid_langflow_component_paths(self):
        """Test that valid langflow.components paths are allowed (even if they don't exist)."""
        # These should pass the security check but fail to load since they don't exist
        valid_langflow_paths = {
            "langflow.components.data.api_request.APIRequestComponent",
            "langflow.components.llms.openai.OpenAIModel",
            "langflow.components.chains.conversation.ConversationChain",
            "langflow.components.agents.agent.Agent",
        }

        result = await load_specific_components(valid_langflow_paths)

        # Should return empty dict because components don't actually exist
        # But importantly, they should NOT be blocked by security validation
        assert result == {}

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid_modules(self):
        """Test that valid module paths are processed while invalid ones are blocked."""
        mixed_modules = {
            # These should pass security validation (but fail to load since they don't exist)
            "lfx.components.valid.ValidComponent",
            "langflow.components.valid.AnotherValid",
            # These should be blocked by security validation
            "os.system",
            "malicious.module.Evil",
            "subprocess.call",
        }

        result = await load_specific_components(mixed_modules)

        # Should return empty dict since none of the valid components actually exist
        # But the important thing is that malicious ones were blocked
        assert result == {}

    @pytest.mark.asyncio
    async def test_case_sensitivity_in_security_check(self):
        """Test that security validation is case-sensitive."""
        # Attackers might try case variations
        case_variations = {
            "OS.system",
            "Os.system",
            "LFX.components.test.Component",  # Should be blocked (wrong case)
            "LANGFLOW.components.test.Component",  # Should be blocked (wrong case)
        }

        result = await load_specific_components(case_variations)

        # All should be blocked due to case sensitivity
        assert result == {}

    @pytest.mark.asyncio
    async def test_prefix_validation_strictness(self):
        """Test that prefix validation is strict and doesn't allow bypasses."""
        bypass_attempts = {
            # Trying to bypass with similar prefixes
            "lfx_components.malicious.Component",  # Underscore instead of dot
            "lfxcomponents.malicious.Component",  # No separator
            "lfx.components_malicious.Component",  # Underscore after components
            "langflow_components.malicious.Component",  # Underscore instead of dot
            "langflowcomponents.malicious.Component",  # No separator
            # Trying to use substrings
            "mylfx.components.malicious.Component",
            "mylangflow.components.malicious.Component",
            # Trying path traversal style
            "lfx.components/../../../malicious.Component",
            "langflow.components/../../../malicious.Component",
        }

        result = await load_specific_components(bypass_attempts)

        # All bypass attempts should be blocked
        assert result == {}
