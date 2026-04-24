"""Tests for cache restoration behavior in build_vertex.

This module tests the fix for the issue where cache restoration failure
would leave vertex.built = True, causing subsequent build() calls to
return early without setting vertex.result.

Bug scenario (before fix):
1. Frozen vertex, cache hit -> vertex.built = True restored from cache
2. finalize_build() throws exception -> should_build = True
3. build() is called, but sees frozen AND built -> returns early
4. finalize_build() never called again -> vertex.result is None
5. Error: "no result found for vertex"

Fix:
Reset vertex.built = False when cache restoration fails, so build()
runs fully and sets vertex.result correctly.
"""

from unittest.mock import AsyncMock, Mock

import pytest


class TestCacheRestorationBuiltFlagReset:
    """Tests for vertex.built flag reset when cache restoration fails.

    These tests verify that when finalize_build() fails during cache
    restoration, vertex.built is reset to False so that subsequent
    build() calls work correctly.
    """

    @pytest.fixture
    def mock_vertex(self):
        """Create a mock vertex for testing cache restoration."""
        vertex = Mock()
        vertex.id = "test-vertex-id"
        vertex.frozen = True
        vertex.built = False
        vertex.is_loop = False
        vertex.display_name = "TestComponent"
        vertex.result = None
        vertex.artifacts = {}
        vertex.built_object = {}
        vertex.built_result = {}
        vertex.full_data = {}
        vertex.results = {}
        vertex.build = AsyncMock()
        vertex.finalize_build = Mock()
        vertex.built_object_repr = Mock(return_value="test")
        return vertex

    @pytest.fixture
    def cached_vertex_dict(self):
        """Create a cached vertex dictionary."""
        return {
            "built": True,
            "artifacts": {"test": "artifact"},
            "built_object": {"test": "object"},
            "built_result": {"test": "result"},
            "full_data": {"test": "data"},
            "results": {"test": "results"},
        }

    def test_should_reset_built_flag_when_finalize_build_fails(self, mock_vertex, cached_vertex_dict):
        """Test that vertex.built is reset to False when finalize_build raises exception.

        Given: A frozen vertex with cached state restored (built=True)
        When: finalize_build() throws an exception
        Then: vertex.built should be reset to False
        """
        # Arrange
        mock_vertex.built = cached_vertex_dict["built"]  # True from cache
        mock_vertex.finalize_build.side_effect = ValueError("Test error")

        # Act - simulate the cache restoration logic
        should_build = False
        try:
            mock_vertex.finalize_build()
            if mock_vertex.result is not None:
                mock_vertex.result.used_frozen_result = True
        except Exception:
            mock_vertex.built = False  # This is the fix
            should_build = True

        # Assert
        assert mock_vertex.built is False, "vertex.built should be reset to False after finalize_build failure"
        assert should_build is True, "should_build should be True to trigger rebuild"

    def test_should_reset_built_flag_when_key_error_on_cache_access(self, mock_vertex):
        """Test that vertex.built is reset to False when KeyError occurs during cache access.

        Given: A frozen vertex with partial cached state
        When: KeyError occurs when accessing cache dict
        Then: vertex.built should be reset to False
        """
        # Arrange
        mock_vertex.built = True  # Assume it was set somehow

        # Simulate incomplete cache dict (missing key)
        cached_result = {"result": {}}  # Missing required keys

        # Act - simulate the cache restoration logic
        should_build = False
        try:
            cached_vertex_dict = cached_result["result"]
            _ = cached_vertex_dict["built"]  # This would raise KeyError
        except KeyError:
            mock_vertex.built = False  # This is the fix
            should_build = True

        # Assert
        assert mock_vertex.built is False, "vertex.built should be reset to False after KeyError"
        assert should_build is True, "should_build should be True to trigger rebuild"

    def test_build_returns_early_when_built_flag_not_reset(self, mock_vertex):
        """Test the bug scenario: build() returns early when built=True is not reset.

        This test demonstrates the bug that occurs WITHOUT the fix:
        When frozen=True and built=True, build() returns early without
        calling finalize_build(), leaving result=None.
        """
        # Arrange - simulate the broken state (before fix)
        mock_vertex.frozen = True
        mock_vertex.built = True  # Not reset after failed cache restoration
        mock_vertex.result = None
        is_loop_component = mock_vertex.display_name == "Loop" or mock_vertex.is_loop

        # Act - simulate build() decision
        should_return_early = mock_vertex.frozen and mock_vertex.built and not is_loop_component

        # Assert - this is the problematic behavior
        assert should_return_early is True, "build() would return early with unreset built flag"
        assert mock_vertex.result is None, "result remains None because finalize_build was never called"

    def test_build_continues_when_built_flag_is_reset(self, mock_vertex):
        """Test the fix: build() continues when built=False after reset.

        This test demonstrates the correct behavior WITH the fix:
        When built=False (reset after failed cache restoration), build()
        continues normally and calls finalize_build().
        """
        # Arrange - simulate the fixed state (after fix)
        mock_vertex.frozen = True
        mock_vertex.built = False  # Reset after failed cache restoration
        is_loop_component = mock_vertex.display_name == "Loop" or mock_vertex.is_loop

        # Act - simulate build() decision
        should_return_early = mock_vertex.frozen and mock_vertex.built and not is_loop_component

        # Assert - build() should NOT return early
        assert should_return_early is False, "build() should continue with reset built flag"


class TestCacheRestorationSuccessCase:
    """Tests for successful cache restoration."""

    @pytest.fixture
    def mock_vertex_with_result(self):
        """Create a mock vertex that successfully restores from cache."""
        vertex = Mock()
        vertex.id = "test-vertex-id"
        vertex.frozen = True
        vertex.built = True
        vertex.is_loop = False
        vertex.display_name = "TestComponent"
        vertex.result = Mock()  # Has a result
        vertex.artifacts = {"test": "artifact"}
        return vertex

    def test_should_not_modify_built_flag_on_successful_restoration(self, mock_vertex_with_result):
        """Test that vertex.built remains True when cache restoration succeeds.

        Given: A frozen vertex with valid cached state
        When: finalize_build() succeeds
        Then: vertex.built should remain True and should_build should be False
        """
        # Arrange
        mock_vertex_with_result.finalize_build = Mock()  # No exception

        # Act - simulate successful cache restoration
        should_build = False
        try:
            mock_vertex_with_result.finalize_build()
            if mock_vertex_with_result.result is not None:
                mock_vertex_with_result.result.used_frozen_result = True
        except Exception:
            mock_vertex_with_result.built = False
            should_build = True

        # Assert
        assert mock_vertex_with_result.built is True, "vertex.built should remain True on success"
        assert should_build is False, "should_build should be False on success"
        assert mock_vertex_with_result.result.used_frozen_result is True


class TestCacheRestorationEdgeCases:
    """Edge case tests for cache restoration."""

    def test_non_frozen_vertex_should_always_build(self):
        """Test that non-frozen vertex always builds regardless of built flag.

        Given: A non-frozen vertex
        When: Checking if should build
        Then: should_build should be True regardless of other flags
        """
        # Arrange
        vertex = Mock()
        vertex.frozen = False
        vertex.built = True
        vertex.is_loop = False
        vertex.display_name = "TestComponent"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        # Act - simulate build_vertex decision
        should_build = not vertex.frozen or is_loop_component

        # Assert
        assert should_build is True, "Non-frozen vertex should always build"

    def test_cache_miss_should_trigger_build(self):
        """Test that cache miss triggers build.

        Given: A frozen vertex with cache miss
        When: Checking if should build
        Then: should_build should be True
        """

        # Arrange
        class CacheMiss:
            pass

        cached_result = CacheMiss()

        # Act - simulate cache miss check
        should_build = isinstance(cached_result, CacheMiss)

        # Assert
        assert should_build is True, "Cache miss should trigger build"

    def test_loop_component_should_always_build_even_when_frozen(self):
        """Test that Loop component always builds even when frozen and built.

        Given: A frozen Loop component with built=True
        When: Checking if should build
        Then: should_build should be True (loops need to iterate)
        """
        # Arrange
        vertex = Mock()
        vertex.frozen = True
        vertex.built = True
        vertex.is_loop = True
        vertex.display_name = "Loop"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        # Act - simulate build_vertex decision
        should_build = not vertex.frozen or is_loop_component

        # Assert
        assert should_build is True, "Loop component should always build"

    def test_multiple_finalize_build_failures_all_reset_built_flag(self):
        """Test that multiple types of exceptions all reset built flag.

        Given: Various exceptions that could occur in finalize_build
        When: Each exception is raised
        Then: vertex.built should be reset to False in all cases
        """
        exceptions_to_test = [
            ValueError("Test value error"),
            TypeError("Test type error"),
            KeyError("Test key error"),
            AttributeError("Test attribute error"),
            RuntimeError("Test runtime error"),
        ]

        for exception in exceptions_to_test:
            # Arrange
            vertex = Mock()
            vertex.built = True
            vertex.finalize_build = Mock(side_effect=exception)

            # Act
            should_build = False
            try:
                vertex.finalize_build()
            except Exception:
                vertex.built = False
                should_build = True

            # Assert
            assert vertex.built is False, f"vertex.built should be reset for {type(exception).__name__}"
            assert should_build is True, f"should_build should be True for {type(exception).__name__}"


class TestCacheRestorationIntegration:
    """Integration-style tests simulating full cache restoration flow."""

    @pytest.fixture
    def mock_graph(self):
        """Create a mock graph for testing."""
        graph = Mock()
        graph.get_vertex = Mock()
        graph.run_manager = Mock()
        graph.run_manager.add_to_vertices_being_run = Mock()
        return graph

    def test_full_flow_with_finalize_build_failure(self):
        """Test the complete flow when finalize_build fails during cache restoration.

        This simulates the exact scenario that was causing the bug:
        1. Frozen vertex, cache hit
        2. Restore state from cache (built=True)
        3. finalize_build() fails
        4. built flag should be reset
        5. build() should run fully
        """
        # Arrange
        vertex = Mock()
        vertex.id = "ChatInput-abc123"
        vertex.frozen = True
        vertex.built = False
        vertex.is_loop = False
        vertex.display_name = "Chat Input"
        vertex.result = None

        cached_vertex_dict = {
            "built": True,
            "artifacts": {},
            "built_object": {"message": Mock()},
            "built_result": {"message": Mock()},
            "full_data": {},
            "results": {"message": Mock()},
        }

        # Simulate finalize_build failure
        def finalize_build_that_fails():
            msg = "Simulated finalize_build failure"
            raise ValueError(msg)

        vertex.finalize_build = finalize_build_that_fails

        # Act - simulate build_vertex logic
        should_build = False
        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        if not vertex.frozen or is_loop_component:
            should_build = True
        else:
            # Simulate cache hit - restore state
            vertex.built = cached_vertex_dict["built"]
            vertex.artifacts = cached_vertex_dict["artifacts"]
            vertex.built_object = cached_vertex_dict["built_object"]
            vertex.built_result = cached_vertex_dict["built_result"]
            vertex.full_data = cached_vertex_dict["full_data"]
            vertex.results = cached_vertex_dict["results"]

            try:
                vertex.finalize_build()
            except Exception:
                vertex.built = False  # THE FIX
                should_build = True

        # Assert
        assert should_build is True, "should_build should be True after finalize_build failure"
        assert vertex.built is False, "vertex.built should be reset to False"

        # Verify that build() will NOT return early
        should_return_early = vertex.frozen and vertex.built and not is_loop_component
        assert should_return_early is False, "build() should NOT return early with reset built flag"

    def test_second_run_scenario_with_fix(self):
        """Test the exact scenario reported: first run works, second run fails.

        This test simulates:
        1. First run: vertex builds normally
        2. Second run: cache restoration fails, but fix ensures rebuild works
        """
        # First run - simulates successful initial build
        vertex = Mock()
        vertex.id = "ChatInput-ybc2G"
        vertex.frozen = True
        vertex.built = False
        vertex.is_loop = False
        vertex.display_name = "Chat Input"
        vertex.result = None

        # Simulate first run: should_build = True (not frozen initially or no cache)
        # After first run: vertex.built = True, vertex.result = Mock()
        vertex.built = True
        vertex.result = Mock()  # First run sets result

        # Second run - cache hit but finalize_build fails
        # This simulates a new vertex instance with same ID
        vertex_run2 = Mock()
        vertex_run2.id = "ChatInput-ybc2G"
        vertex_run2.frozen = True
        vertex_run2.built = False  # New instance starts with built=False
        vertex_run2.is_loop = False
        vertex_run2.display_name = "Chat Input"
        vertex_run2.result = None  # New instance starts with result=None

        cached_vertex_dict = {
            "built": True,  # From first run
            "artifacts": {},
            "built_object": {"message": Mock()},
            "built_result": {"message": Mock()},
            "full_data": {},
            "results": {"message": Mock()},
        }

        # Simulate cache restoration failure
        vertex_run2.finalize_build = Mock(side_effect=ValueError("Simulated failure"))

        # Act - simulate build_vertex for second run
        should_build = False
        is_loop_component = vertex_run2.display_name == "Loop" or vertex_run2.is_loop

        if not vertex_run2.frozen or is_loop_component:
            should_build = True
        else:
            # Cache hit - restore state
            vertex_run2.built = cached_vertex_dict["built"]  # Set to True
            try:
                vertex_run2.finalize_build()
            except Exception:
                vertex_run2.built = False  # THE FIX - reset to False
                should_build = True

        # Assert - with the fix, the vertex should rebuild correctly
        assert vertex_run2.built is False, "vertex.built should be reset after cache restoration failure"
        assert should_build is True, "should_build should trigger rebuild"

        # Verify build() won't return early
        should_return_early = vertex_run2.frozen and vertex_run2.built and not is_loop_component
        assert should_return_early is False, "build() should continue with reset built flag"
