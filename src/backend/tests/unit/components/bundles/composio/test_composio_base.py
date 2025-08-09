import asyncio
import logging
import os
from contextlib import suppress
from unittest.mock import patch

import pytest
from composio import Composio
from langflow.base.composio.composio_base import ComposioBaseComponent

from tests.base import DID_NOT_EXIST, ComponentTestBase, VersionComponentMapping

# Set up logging for the test
logger = logging.getLogger(__name__)


class TestComposioComponentAuth(ComponentTestBase):
    """Integration test for ComposioBaseComponent using real API calls."""

    @pytest.fixture
    def component_class(self):
        return ComposioBaseComponent

    @pytest.fixture
    def default_kwargs(self):
        # Get API key from environment - make sure to set COMPOSIO_API_KEY in your .env file
        # This test requires an existing Gmail connection and no existing GitHub connection
        api_key = os.getenv("COMPOSIO_API_KEY")
        if not api_key:
            pytest.skip("COMPOSIO_API_KEY environment variable not set")

        return {
            "entity_id": "default",
            "api_key": api_key,
            "app_name": "GMAIL",
            "action_button": "disabled",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            VersionComponentMapping(version="1.1.1", module="base.composio", file_name=DID_NOT_EXIST),
            VersionComponentMapping(version="1.1.0", module="base.composio", file_name=DID_NOT_EXIST),
            VersionComponentMapping(version="1.0.19", module="base.composio", file_name=DID_NOT_EXIST),
        ]

    @pytest.mark.asyncio
    async def test_composio_integration_real_api_calls(self):
        """Integration test that mimics composio_base.py flow with real API calls.

        Flow:
        1. Validate API Key (real API call)
        2. Check for existing connections (real API call)
        3a. If connection found -> Success (GMAIL scenario)
        3b. If no connection -> Initiate real OAuth flow (GITHUB scenario)
        4. Mock final status check (since real OAuth completion isn't possible)
        """
        # Track resources created during testing for cleanup
        created_connection_id = None
        created_auth_config_id = None

        # Test both scenarios: existing connection (Gmail) and new connection (GitHub)
        test_cases = [
            {"app_name": "GMAIL", "expected_has_connection": True},
            {"app_name": "GITHUB", "expected_has_connection": False},
        ]

        for test_case in test_cases:
            app_name = test_case["app_name"]
            expected_has_connection = test_case["expected_has_connection"]

            logger.info("Testing %s integration - expecting connection: %s", app_name, expected_has_connection)

            # Set up component with API key
            api_key = os.getenv("COMPOSIO_API_KEY")
            if not api_key:
                pytest.skip("COMPOSIO_API_KEY environment variable not set")

            default_kwargs = {
                "entity_id": "default",
                "api_key": api_key,
                "app_name": app_name,
                "action_button": "disabled",
            }

            component = await self.component_setup(ComposioBaseComponent, default_kwargs)

            # Step 1: Validate API Key
            logger.info("Validating API key...")
            wrapper = component._build_wrapper()
            assert wrapper is not None, "API Key validation failed"
            logger.info("API key validation successful")

            # Step 2: Check for existing connections
            logger.info("Checking for existing connections...")
            active_connection = component._find_active_connection_for_app(app_name)

            if expected_has_connection:
                # Scenario: Connection already exists (Gmail)
                assert active_connection is not None, "Expected to find existing connection"
                connection_id, status = active_connection
                logger.info("Found existing connection: %s with status: %s", connection_id, status)

                # Step 4: Monitor connection stability
                logger.info("Monitoring connection %s for stability...", connection_id)
                start_time = asyncio.get_event_loop().time()
                max_wait_time = 5  # 5 seconds max
                check_interval = 1  # Check every 1 second

                while asyncio.get_event_loop().time() - start_time < max_wait_time:
                    try:
                        # Query the connection status using the Composio API
                        connection_status = wrapper.connected_accounts.get(connection_id)
                        current_status = connection_status.status if connection_status else None

                        if current_status == "ACTIVE":
                            logger.debug("Connection %s is still ACTIVE", connection_id)
                        elif current_status == "INITIATED":
                            logger.debug("Connection %s is INITIATED, waiting for activation...", connection_id)
                        elif current_status == "DISCONNECTED":
                            logger.warning("Connection %s has been DISCONNECTED!", connection_id)
                            break
                        elif current_status is None:
                            logger.warning("Connection %s no longer exists (removed)!", connection_id)
                            break
                        else:
                            logger.debug("Connection %s status: %s", connection_id, current_status)

                    except Exception:
                        logger.exception("Error checking connection %s", connection_id)
                        break

                    await asyncio.sleep(check_interval)

                # Step 5: Test tool execution with existing connection
                logger.info("Testing tool execution with existing connection...")
                with suppress(Exception):
                    # Execute GMAIL_FETCH_EMAILS tool to verify connection works
                    result = wrapper.tools.execute(slug="GMAIL_FETCH_EMAILS", arguments={}, user_id="default")

                    if isinstance(result, dict) and "successful" in result:
                        if result["successful"]:
                            logger.info("Tool execution successful")
                        else:
                            error_msg = result.get("error", "Tool execution failed")
                            logger.error("Tool execution failed: %s", error_msg)
                    else:
                        logger.info("Tool execution successful")

            else:
                # Scenario: No existing connection (GitHub)
                assert active_connection is None, "Expected no existing connection"
                logger.info("No existing connection found, initiating OAuth flow...")

                # Mock the connection status check since we can't complete OAuth in tests
                with patch.object(component, "_check_connection_status_by_id") as mock_status_check:
                    mock_status_check.return_value = "ACTIVE"  # Mock successful completion

                    # Initiate OAuth connection
                    redirect_url, connection_id = component._initiate_connection(app_name)

                    assert redirect_url is not None, "Expected redirect URL from OAuth initiation"
                    assert connection_id is not None, "Expected connection ID from OAuth initiation"
                    logger.info("OAuth initiated - Redirect URL: %s", redirect_url)
                    logger.info("Connection ID: %s", connection_id)

                    # Store connection ID for cleanup
                    created_connection_id = connection_id

                    # Get the auth config ID for cleanup
                    with suppress(Exception):
                        auth_configs = wrapper.auth_configs.list()
                        if auth_configs.items:
                            created_auth_config_id = auth_configs.items[0].id
                            logger.info("Auth config ID: %s", created_auth_config_id)

                    # Verify the mocked connection status
                    status = component._check_connection_status_by_id(connection_id)
                    assert status == "ACTIVE", "Expected ACTIVE status (mocked)"
                    logger.info("Connection status: %s (mocked)", status)
                    mock_status_check.assert_called_once_with(connection_id)

            logger.info("%s integration test completed successfully", app_name)

        # Cleanup: Delete test resources to ensure repeatability
        logger.info("Cleaning up test resources...")
        if created_connection_id or created_auth_config_id:
            with suppress(Exception):
                # Use the same API key for cleanup
                api_key = os.getenv("COMPOSIO_API_KEY")
                if not api_key:
                    logger.warning("COMPOSIO_API_KEY not set, skipping cleanup")
                    return

                composio = Composio(api_key=api_key)

                # Delete the connection and auth config created during testing
                if created_connection_id:
                    with suppress(Exception):
                        composio.connected_accounts.delete(created_connection_id)
                        logger.info("Connection deleted: %s", created_connection_id)

                if created_auth_config_id:
                    with suppress(Exception):
                        composio.auth_configs.delete(created_auth_config_id)
                        logger.info("Auth config deleted: %s", created_auth_config_id)
        else:
            logger.info("No resources were created during this test run")

        logger.info("Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])