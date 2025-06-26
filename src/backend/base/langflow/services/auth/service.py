"""Minimal authentication service implementation.

This module contains the AuthService class, which serves as a lightweight
service wrapper around authentication settings. The service itself contains
minimal logic and primarily acts as a dependency injection container.

The actual authentication logic is implemented in:
- `langflow.services.auth.utils` for user creation and validation
- `langflow.api.utils` for request authentication decorators
- `langflow.services.database.models.user` for user data models

Example:
    >>> from langflow.services.deps import get_settings_service
    >>> settings_service = get_settings_service()
    >>> auth_service = AuthService(settings_service)
    >>> auth_service.settings_service.auth_settings.AUTO_LOGIN
    True

The service provides access to authentication configuration through
`settings_service.auth_settings` which includes options like AUTO_LOGIN,
SECRET_KEY, and session configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class AuthService(Service):
    name = "auth_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
