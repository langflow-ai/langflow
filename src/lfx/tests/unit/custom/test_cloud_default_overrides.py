"""Tests for cloud-mode default overrides on mixed compatibility components."""

from lfx.components.tools.searxng import SearXNGToolComponent


def test_searxng_component_clears_localhost_default_in_cloud_mode():
    assert SearXNGToolComponent.metadata["cloud_default_overrides"] == {
        "url": {"value": "", "placeholder": "Enter SearXNG URL"},
    }
