"""General settings defaults."""

from __future__ import annotations

from lfx.services.settings.base import Settings


def test_background_metrics_interval_default():
    settings = Settings()
    assert settings.background_metrics_interval == 15
    assert settings.background_metrics_interval > 0
