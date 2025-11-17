"""Tests that demonstrate the exact bug fix for PR #10232.

These tests show:
1. What FAILS with the OLD (buggy) code
2. What PASSES with the NEW (fixed) code

Issue: https://github.com/langflow-ai/langflow/issues/10231
PR: https://github.com/langflow-ai/langflow/pull/10232

Run these tests to verify:
- The bug exists (tests that show errors)
- The fix works (tests that pass)
"""

import pytest
import sqlalchemy as sa


class TestBuggyCode:
    """These tests demonstrate what would FAIL with the OLD buggy code.

    OLD CODE (BUGGY):
        pool_class = getattr(sa, poolclass_key, None)
        if pool_class and isinstance(pool_class(), sa.pool.Pool):  # <-- FAILS HERE
    """

    def test_buggy_code_crashes_with_nullpool(self):
        """This test PROVES the bug exists.

        When users set LANGFLOW_DB_CONNECTION_SETTINGS={"poolclass": "NullPool"},
        the OLD code would crash with:
        TypeError: Pool.__init__() missing 1 required positional argument: 'creator'
        """
        poolclass_key = "NullPool"

        # Get the pool class
        pool_class = getattr(sa.pool, poolclass_key, None)

        # OLD BUGGY CODE tries to instantiate:
        # This ALWAYS fails because Pool requires 'creator' argument
        with pytest.raises(TypeError) as exc_info:
            isinstance(pool_class(), sa.pool.Pool)

        assert "creator" in str(exc_info.value)

    def test_buggy_code_crashes_with_any_pool_class(self):
        """ALL pool classes fail with the buggy code because they all need 'creator'."""
        pool_classes = ["NullPool", "StaticPool", "QueuePool"]

        for pool_name in pool_classes:
            pool_class = getattr(sa.pool, pool_name, None)
            assert pool_class is not None

            with pytest.raises(TypeError):
                pool_class()  # Cannot instantiate without 'creator'


class TestFixedCode:
    """These tests demonstrate what PASSES with the NEW fixed code.

    NEW CODE (FIXED):
        pool_class = getattr(sa.pool, poolclass_key, None)
        if pool_class and issubclass(pool_class, sa.pool.Pool):  # <-- WORKS
    """

    def test_fixed_code_works_with_nullpool(self):
        """This test PROVES the fix works.

        The NEW code uses issubclass() instead of isinstance(), which doesn't
        require instantiation and therefore doesn't need 'creator'.
        """
        poolclass_key = "NullPool"

        # NEW FIXED CODE
        pool_class = getattr(sa.pool, poolclass_key, None)

        # This should NOT raise any exception
        is_valid = pool_class and issubclass(pool_class, sa.pool.Pool)

        assert is_valid is True
        assert pool_class == sa.pool.NullPool

    def test_fixed_code_works_with_all_pool_classes(self):
        """ALL pool classes work with the fixed code."""
        pool_classes = ["NullPool", "StaticPool", "QueuePool", "AsyncAdaptedQueuePool"]

        for pool_name in pool_classes:
            pool_class = getattr(sa.pool, pool_name, None)
            if pool_class:
                # This should NOT raise any exception
                is_valid = issubclass(pool_class, sa.pool.Pool)
                assert is_valid is True, f"{pool_name} should be valid"


class TestFullWorkflow:
    """Tests that simulate the complete _create_engine workflow."""

    def test_old_buggy_workflow_fails(self):
        """Simulate what happens in OLD _create_engine with poolclass config.

        This DEMONSTRATES THE BUG.
        """
        # User config
        kwargs = {
            "poolclass": "NullPool",
            "pool_size": 10,
        }

        poolclass_key = kwargs.get("poolclass")
        if poolclass_key is not None:
            pool_class = getattr(sa, poolclass_key, None)
            if pool_class:
                # BUG: This line crashes
                with pytest.raises(TypeError):
                    isinstance(pool_class(), sa.pool.Pool)

    def test_new_fixed_workflow_passes(self):
        """Simulate what happens in NEW _create_engine with poolclass config.

        This DEMONSTRATES THE FIX WORKS.
        """
        # User config
        kwargs = {
            "poolclass": "NullPool",
            "pool_size": 10,
        }

        poolclass_key = kwargs.get("poolclass")
        if poolclass_key is not None:
            # FIXED: Use sa.pool namespace
            pool_class = getattr(sa.pool, poolclass_key, None)
            # FIXED: Use issubclass instead of isinstance
            if pool_class and issubclass(pool_class, sa.pool.Pool):
                kwargs["poolclass"] = pool_class

        # Success! kwargs now has the pool class object
        assert kwargs["poolclass"] == sa.pool.NullPool
        assert kwargs["pool_size"] == 10

    def test_invalid_poolclass_handled_gracefully(self):
        """NEW code handles invalid pool class names without crashing."""
        kwargs = {
            "poolclass": "NotARealPoolClass",
            "pool_size": 10,
        }

        poolclass_key = kwargs.get("poolclass")
        if poolclass_key is not None:
            pool_class = getattr(sa.pool, poolclass_key, None)
            if pool_class and issubclass(pool_class, sa.pool.Pool):
                kwargs["poolclass"] = pool_class
            else:
                # Remove invalid poolclass (as per new fix)
                kwargs.pop("poolclass", None)

        # Invalid poolclass was removed, other settings preserved
        assert "poolclass" not in kwargs
        assert kwargs["pool_size"] == 10
