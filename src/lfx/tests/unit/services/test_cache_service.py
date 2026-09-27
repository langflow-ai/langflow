"""Regression tests: ThreadingInMemoryCache must never unpickle stored bytes (H1-3982189)."""

import pickle

from lfx.services.cache.service import ThreadingInMemoryCache

_MARKERS: list[str] = []


def _gadget_side_effect(marker: str) -> str:
    """Module-level callable used as a pickle reduce gadget in the test below."""
    _MARKERS.append(marker)
    return marker


class _Gadget:
    """A picklable object whose deserialization would run _gadget_side_effect."""

    def __init__(self, marker: str) -> None:
        self.marker = marker

    def __reduce__(self):
        return (_gadget_side_effect, (self.marker,))


class TestThreadingInMemoryCacheDeserialization:
    def test_bytes_value_is_returned_as_is_without_unpickling(self):
        _MARKERS.clear()
        cache = ThreadingInMemoryCache()
        payload = pickle.dumps(_Gadget("gadget-ran"))
        cache.set("k", payload)

        result = cache.get("k")

        assert result == payload  # raw bytes returned, never unpickled
        assert _MARKERS == []  # reduce gadget never executed

    def test_normal_values_round_trip(self):
        cache = ThreadingInMemoryCache()
        cache.set("k", {"a": [1, 2]})
        assert cache.get("k") == {"a": [1, 2]}
