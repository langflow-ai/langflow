"""Shared fixtures for the split authorization-helper tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest


@pytest.fixture
def fake_user():
    """Build a non-superuser user object compatible with ensure_permission."""
    return SimpleNamespace(id=uuid4(), is_superuser=False)


@pytest.fixture
def fake_superuser():
    """Build a superuser user object compatible with ensure_permission."""
    return SimpleNamespace(id=uuid4(), is_superuser=True)
