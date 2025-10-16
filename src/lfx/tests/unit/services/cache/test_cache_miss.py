"""Tests for CacheMiss sentinel class behavior."""

import pytest

from lfx.services.cache.utils import CACHE_MISS, CacheMiss


class TestCacheMiss:
    """Test CacheMiss class behavior."""

    def test_cache_miss_singleton_exists(self):
        """Test that CACHE_MISS singleton is created."""
        assert CACHE_MISS is not None
        assert isinstance(CACHE_MISS, CacheMiss)

    def test_cache_miss_bool_is_false(self):
        """Test that CacheMiss evaluates to False in boolean context."""
        assert not CACHE_MISS
        assert bool(CACHE_MISS) is False

    def test_cache_miss_in_if_statement(self):
        """Test that CacheMiss works correctly in if statements."""
        result = CACHE_MISS

        if result:
            pytest.fail("CACHE_MISS should evaluate to False")
        else:
            # This branch should execute
            assert True

    def test_cache_miss_in_not_check(self):
        """Test that 'if not result' works correctly with CACHE_MISS."""
        result = CACHE_MISS

        if not result:
            # This branch should execute
            assert True
        else:
            pytest.fail("'not CACHE_MISS' should be True")

    def test_cache_miss_repr(self):
        """Test that CacheMiss has a clear string representation."""
        assert repr(CACHE_MISS) == "<CACHE_MISS>"
        assert str(CACHE_MISS) == "<CACHE_MISS>"

    def test_cache_miss_identity_check(self):
        """Test that identity check works with CACHE_MISS."""
        result = CACHE_MISS

        if result is CACHE_MISS:
            assert True
        else:
            pytest.fail("Identity check should work")

    def test_cache_miss_vs_none(self):
        """Test that CACHE_MISS is different from None."""
        assert CACHE_MISS is not None
        assert CACHE_MISS != None  # noqa: E711

        # But both are falsy
        assert not CACHE_MISS
        assert not None

    def test_cache_miss_singleton_pattern(self):
        """Test that CACHE_MISS is a singleton."""
        # Creating a new instance should give us a different object
        # but CACHE_MISS itself should be the same everywhere
        new_instance = CacheMiss()
        assert new_instance is not CACHE_MISS  # Different instances
        assert not new_instance  # But same falsy behavior
        assert repr(new_instance) == "<CACHE_MISS>"  # Same repr

    def test_cache_miss_in_conditional_expression(self):
        """Test CACHE_MISS in ternary/conditional expressions."""
        result = CACHE_MISS
        value = "found" if result else "not found"
        assert value == "not found"

    def test_cache_miss_with_or_operator(self):
        """Test CACHE_MISS with 'or' operator for default values."""
        result = CACHE_MISS
        default_value = "default"

        # This is a common pattern: use default if cache miss
        value = result or default_value
        assert value == default_value

    def test_cache_miss_in_list_comprehension(self):
        """Test filtering CACHE_MISS in list comprehensions."""
        results = [1, 2, CACHE_MISS, 3, CACHE_MISS, 4]
        filtered = [r for r in results if r]

        assert filtered == [1, 2, 3, 4]
        assert CACHE_MISS not in filtered
