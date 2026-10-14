"""``check_rate_limit`` counts over a minute by default, or over an hour on request.

The hour window exists for callers whose own cap is hourly - Slack delivers at
most 30,000 events per workspace per app per hour, and bursts inside that hour
freely - so a per-minute ceiling would refuse traffic the sender is allowed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langflow.services.rate_limit.service import check_rate_limit
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


def _request() -> SimpleNamespace:
    limiter = Limiter(key_func=lambda _request: "198.51.100.7", storage_uri="memory://")
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(limiter=limiter)))


def test_an_hourly_limit_is_counted_over_the_hour() -> None:
    request = _request()

    check_rate_limit(request, scope="hourly", key="slack-team:app:T1", limit_per_hour=2)
    check_rate_limit(request, scope="hourly", key="slack-team:app:T1", limit_per_hour=2)
    with pytest.raises(RateLimitExceeded) as refused:
        check_rate_limit(request, scope="hourly", key="slack-team:app:T1", limit_per_hour=2)

    assert str(refused.value.limit.limit) == "2 per 1 hour"


def test_a_per_minute_limit_is_still_counted_over_the_minute() -> None:
    request = _request()

    check_rate_limit(request, scope="minutely", limit_per_minute=1)
    with pytest.raises(RateLimitExceeded) as refused:
        check_rate_limit(request, scope="minutely", limit_per_minute=1)

    assert str(refused.value.limit.limit) == "1 per 1 minute"


def test_a_limit_names_one_window() -> None:
    with pytest.raises(ValueError, match="not both"):
        check_rate_limit(_request(), scope="both", limit_per_minute=1, limit_per_hour=1)
