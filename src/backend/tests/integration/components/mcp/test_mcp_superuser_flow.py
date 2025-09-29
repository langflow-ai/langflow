import pytest
from langflow.services.auth.utils import create_user_longterm_token
from langflow.services.deps import get_db_service, get_settings_service
from langflow.services.utils import initialize_services


@pytest.mark.skip(reason="MCP Projects can only create long-term tokens if AUTO_LOGIN is enabled")
async def test_mcp_longterm_token_headless_superuser_integration():
    """Integration-style check that without explicit credentials, AUTO_LOGIN=false path.

    Creates a headless superuser via initialize_services and allows minting a long-term token.
    """
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = ""
    settings.auth_settings.SUPERUSER_PASSWORD = ""

    await initialize_services()

    async with get_db_service().with_session() as session:
        user_id, tokens = await create_user_longterm_token(session)
        assert user_id is not None
        assert tokens.get("access_token")
