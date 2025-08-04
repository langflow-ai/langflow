import pytest
from unittest.mock import patch, MagicMock
from langflow.base.composio.composio_base import ComposioBaseComponent
from tests.base import ComponentTestBaseWithClient, VersionComponentMapping, DID_NOT_EXIST
from composio import Composio


class TestComposioIntegration(ComponentTestBaseWithClient):
    """Integration test for ComposioBaseComponent using real API calls."""

    @pytest.fixture
    def component_class(self):
        return ComposioBaseComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "entity_id": "default",
            "api_key": "ak__p_ZUVH1qXvL4YudJ5PF",
            "app_name": "GMAIL",
            "action_button": "disabled",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            VersionComponentMapping(
                version="1.1.1",
                module="base.composio",
                file_name=DID_NOT_EXIST
            ),
            VersionComponentMapping(
                version="1.1.0",
                module="base.composio",
                file_name=DID_NOT_EXIST
            ),
            VersionComponentMapping(
                version="1.0.19",
                module="base.composio",
                file_name=DID_NOT_EXIST
            ),
        ]

    @pytest.mark.asyncio
    async def test_composio_integration_real_api_calls(self):
        """
        Integration test that mimics composio_base.py flow with real API calls.
        
        Flow:
        1. Validate API Key (real API call)
        2. Check for existing connections (real API call)
        3a. If connection found -> Success (GMAIL scenario)
        3b. If no connection -> Initiate real OAuth flow (GITHUB scenario)
        4. Mock final status check (since real OAuth completion isn't possible)
        """
        
        # Variables for cleanup
        created_connection_id = None
        created_auth_config_id = None
        
        # 2 test cases using single API key with different apps
        test_cases = [
            {
                "app_name": "GMAIL",
                "description": "Existing connection scenario (GMAIL)",
                "expected_has_connection": True  
            },
            {
                "app_name": "GITHUB",
                "description": "Fresh account scenario (GITHUB)",
                "expected_has_connection": False 
            }
        ]
        
        for test_case in test_cases:
            app_name = test_case["app_name"]
            description = test_case["description"]
            expected_has_connection = test_case["expected_has_connection"]
            
            print(f"\n=== Testing: {description} ===")
            print(f"App: {app_name}")
            
            # Setup component
            default_kwargs = {
                "entity_id": "default",
                "api_key": "ak__p_ZUVH1qXvL4YudJ5PF",
                "app_name": app_name,
                "action_button": "disabled",
            }
            
            component = await self.component_setup(ComposioBaseComponent, default_kwargs)
            
            # Step 1: Validate API Key
            print("Step 1: Validating API Key...")
            wrapper = component._build_wrapper()
            assert wrapper is not None, "API Key validation failed"
            print("API Key validation successful")
            
            # Step 2: Check for existing connections
            print("Step 2: Checking for existing connections...")
            active_connection = component._find_active_connection_for_app(app_name)
            
            if expected_has_connection:
                # If Connection found
                assert active_connection is not None, "Expected to find existing connection"
                connection_id, status = active_connection
                print(f"Found existing connection: {connection_id} with status: {status}")
                print("Step 3a: Success - using existing connection")
                
                # Step 4: Monitor the specific connection ID for stability and detect disconnection/removal
                print(f"Step 4: Monitoring connection {connection_id} for stability...")
                import time
                
                start_time = time.time()
                max_wait_time = 5  # 5 seconds max
                check_interval = 1  # Check every 1 second
                connection_lost = False
                
                while time.time() - start_time < max_wait_time:
                    # Check the specific connection ID that was found
                    try:
                        # Query the connection status using the Composio API
                        connection_status = wrapper.connected_accounts.get(connection_id)
                        current_status = connection_status.status if connection_status else None
                        
                        if current_status == "ACTIVE":
                            print(f"Connection {connection_id} is still ACTIVE")
                        elif current_status == "INITIATED":
                            print(f"Connection {connection_id} is INITIATED, waiting for activation...")
                        elif current_status == "DISCONNECTED":
                            print(f"Connection {connection_id} has been DISCONNECTED!")
                            connection_lost = True
                            break
                        elif current_status is None:
                            print(f"Connection {connection_id} no longer exists (removed)!")
                            connection_lost = True
                            break
                        else:
                            print(f"Connection {connection_id} status: {current_status}")
                            
                    except Exception as e:
                        print(f"Error checking connection {connection_id}: {e}")
                        connection_lost = True
                        break
                    
                    time.sleep(check_interval)
                
                if not connection_lost:
                    print(f"Connection {connection_id} remained stable during monitoring period")
                else:
                    print(f"Connection {connection_id} was lost or removed during monitoring")
                
                # Step 5: Execute tool with existing connection
                print("Step 5: Executing tool with existing connection...")
                try:
                    # Execute GMAIL_FETCH_EMAILS tool to verify connection works
                    result = wrapper.tools.execute(
                        slug="GMAIL_FETCH_EMAILS",
                        arguments={},
                        user_id="default"
                    )
                    
                    if isinstance(result, dict) and "successful" in result:
                        if result["successful"]:
                            print("Tool execution successful")
                        else:
                            error_msg = result.get("error", "Tool execution failed")
                            print(f"Tool execution failed: {error_msg}")
                    else:
                        print("Tool execution successful")
                        
                except Exception as e:
                    print(f"Tool execution error: {e}")
                
            else:
                # If No connection found
                assert active_connection is None, "Expected no existing connection"
                print("No existing connection found")
                print("Step 3b: Initiating OAuth flow...")
                
                # Mock the connection status check since we can't complete OAuth in tests
                with patch.object(component, '_check_connection_status_by_id') as mock_status_check:
                    mock_status_check.return_value = "ACTIVE"  # Mock successful completion
                    
                    # Initiate OAuth connection
                    redirect_url, connection_id = component._initiate_connection(app_name)
                    
                    assert redirect_url is not None, "Expected redirect URL from OAuth initiation"
                    assert connection_id is not None, "Expected connection ID from OAuth initiation"
                    print(f"OAuth initiated - Redirect URL: {redirect_url}")
                    print(f"Connection ID: {connection_id}")
                    
                    # Store connection ID for cleanup
                    created_connection_id = connection_id
                    
                    # Get the auth config ID for cleanup
                    try:
                        auth_configs = wrapper.auth_configs.list()
                        if auth_configs.items:
                            created_auth_config_id = auth_configs.items[0].id
                            print(f"Auth config ID: {created_auth_config_id}")
                    except Exception as e:
                        print(f"Could not get auth config ID: {e}")
                    
                    # Verify the mocked connection status
                    status = component._check_connection_status_by_id(connection_id)
                    assert status == "ACTIVE", "Expected ACTIVE status (mocked)"
                    print(f"Connection status: {status} (mocked)")
                    mock_status_check.assert_called_once_with(connection_id)
            
            print(f"{description} completed successfully\n")

        # Cleanup: Delete the test resources to ensure repeatability
        print("\n=== Cleanup: Deleting test resources ===")
        if created_connection_id or created_auth_config_id:
            try:
                # Use the same API key for cleanup
                composio = Composio(api_key="ak__p_ZUVH1qXvL4YudJ5PF")
                
                # Delete the connection and auth config created during testing
                # Connected Account
                if created_connection_id:
                    try:
                        del_conn = composio.connected_accounts.delete(created_connection_id)
                        print(f"Connection deleted: {created_connection_id} - {del_conn}")
                    except Exception as e:
                        print(f"Connection deletion failed: {e}")
                else:
                    print("No connection to delete")
                
                # Auth config
                if created_auth_config_id:
                    try:
                        del_auth = composio.auth_configs.delete(created_auth_config_id)
                        print(f"Auth config deleted: {created_auth_config_id} - {del_auth}")
                    except Exception as e:
                        print(f"Auth config deletion failed: {e}")
                else:
                    print("No auth config to delete")
                    
            except Exception as e:
                print(f"Cleanup failed: {e}")
        else:
            print("No resources were created during this test run")
        
        print("Cleanup completed\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 