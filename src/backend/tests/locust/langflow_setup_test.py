#!/usr/bin/env python3
"""Langflow Load Test Setup CLI

This script sets up a complete Langflow test environment by:
1. Starting Langflow (optional)
2. Creating a test user account
3. Authenticating and getting JWT tokens
4. Creating API keys
5. Loading a real starter project flow
6. Providing credentials for load testing

Usage:
    python setup_langflow_test.py --help
    python setup_langflow_test.py --interactive
    python setup_langflow_test.py --flow "Basic Prompting"
    python setup_langflow_test.py --list-flows
"""

import argparse
import asyncio
import json
import sys
import time


async def get_starter_projects_from_api(host: str, access_token: str) -> list[dict]:
    """Get starter projects from Langflow API."""
    import httpx

    # Ensure proper URL formatting
    base_host = host.rstrip("/")
    url = f"{base_host}/api/v1/starter-projects/"
    print(f"   🔍 Fetching starter projects from: {url}")

    try:
        async with httpx.AsyncClient() as client:
            # Try with authentication first
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            print(f"   📡 Response status: {response.status_code}")

            # If auth fails, try without authentication (some endpoints might be public)
            if response.status_code == 401:
                print("   🔄 Trying without authentication...")
                response = await client.get(url, timeout=30.0)
                print(f"   📡 Response status (no auth): {response.status_code}")

            if response.status_code != 200:
                print(f"⚠️  Failed to get starter projects: {response.status_code}")
                print(f"Response: {response.text}")
                return []

            # Check if response is empty
            if not response.text.strip():
                print("⚠️  Empty response from starter projects endpoint")
                return []

            data = response.json()
            print(f"   ✅ Found {len(data)} starter projects")
            return data

    except Exception as e:
        print(f"⚠️  Error fetching starter projects: {e}")
        if hasattr(e, "response"):
            print(f"   Status code: {e.response.status_code}")
            print(f"   Response text: {e.response.text}")
        return []


async def list_available_flows(host: str, access_token: str) -> list[tuple[str, str, str]]:
    """List all available starter project flows from Langflow API.

    Args:
        host: Langflow host URL
        access_token: JWT access token for authentication

    Returns:
        List of tuples: (flow_name, flow_name, description)
    """
    projects = await get_starter_projects_from_api(host, access_token)

    # Known starter project names and descriptions based on the source code
    known_projects = [
        (
            "Basic Prompting",
            "Basic Prompting",
            "A simple chat interface with OpenAI that answers like a pirate ✅ Great for load testing",
        ),
        (
            "Blog Writer",
            "Blog Writer",
            "Generate blog posts using web content as reference material ✅ Good for load testing",
        ),
        (
            "Document Q&A",
            "Document Q&A",
            "Question and answer system for document content ⚠️  Requires file uploads - not ideal for load testing",
        ),
        ("Memory Chatbot", "Memory Chatbot", "Chatbot with conversation memory using context ✅ Good for load testing"),
        (
            "Vector Store RAG",
            "Vector Store RAG",
            "Retrieval-Augmented Generation with vector storage ⚠️  May require setup - test first",
        ),
    ]

    # Return the known projects if we have the expected number
    if len(projects) == len(known_projects):
        return known_projects

    # Fallback: generate names based on project count
    flows: list[tuple[str, str, str]] = []
    for i, project in enumerate(projects):
        if i < len(known_projects):
            flow_name, name, description = known_projects[i]
        else:
            flow_name = f"Starter Project {i + 1}"
            name = flow_name
            description = "Starter project flow"

        flows.append((flow_name, name, description))

    return flows


async def get_flow_data_by_name(host: str, access_token: str, flow_name: str) -> dict | None:
    """Get flow data for a specific starter project by name.

    Args:
        host: Langflow host URL
        access_token: JWT access token for authentication
        flow_name: Name of the flow to retrieve

    Returns:
        Flow data as dictionary, or None if not found
    """
    projects = await get_starter_projects_from_api(host, access_token)
    flows = await list_available_flows(host, access_token)

    # Find the project by name and get its index
    for i, (fname, name, _) in enumerate(flows):
        if name == flow_name:
            if i < len(projects):
                # Add the name and description to the project data
                project_data = projects[i].copy()
                project_data["name"] = name
                project_data["description"] = flows[i][2]
                return project_data

    print(f"⚠️  Flow '{flow_name}' not found in starter projects")
    return None


async def select_flow_interactive(host: str, access_token: str) -> str | None:
    """Interactive flow selection."""
    flows = await list_available_flows(host, access_token)

    if not flows:
        print("❌ No starter project flows found!")
        return None

    print(f"\n{'=' * 80}")
    print("AVAILABLE STARTER PROJECT FLOWS")
    print(f"{'=' * 80}")

    for i, (flow_name, name, description) in enumerate(flows, 1):
        print(f"{i:2d}. {name}")
        print(f"    {description[:70]}{'...' if len(description) > 70 else ''}")
        print()

    while True:
        try:
            choice = input(f"Select a flow (1-{len(flows)}) or 'q' to quit: ").strip()
            if choice.lower() == "q":
                return None

            choice_num = int(choice)
            if 1 <= choice_num <= len(flows):
                selected_flow = flows[choice_num - 1]
                print(f"\n✅ Selected: {selected_flow[1]}")
                return selected_flow[0]  # Return flow name
            print(f"Please enter a number between 1 and {len(flows)}")
        except ValueError:
            print("Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n\nSetup cancelled by user")
            return None


async def setup_langflow_environment(host: str, flow_name: str | None = None, interactive: bool = False) -> dict:
    """Set up complete Langflow environment with real starter project flows."""
    try:
        import httpx
    except ImportError:
        print("❌ Missing dependency: httpx")
        print("Install with: pip install httpx")
        sys.exit(1)

    # Configuration - use default Langflow credentials
    username = "langflow"
    password = "langflow"

    setup_state = {
        "host": host,
        "username": username,
        "password": password,
        "user_id": None,
        "access_token": None,
        "api_key": None,
        "flow_id": None,
        "flow_name": None,
        "flow_data": None,
    }

    async with httpx.AsyncClient(base_url=host, timeout=60.0) as client:
        # Step 1: Health check
        print(f"\n1. Checking Langflow health at {host}...")
        try:
            health_response = await client.get("/health")
            if health_response.status_code != 200:
                raise Exception(f"Health check failed: {health_response.status_code}")
            print("   ✅ Langflow is running and accessible")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
            raise

        # Step 2: Skip user creation, use default credentials
        print("2. Using default Langflow credentials...")
        print(f"   ✅ Using username: {username}")

        # Step 3: Login to get JWT token
        print("3. Authenticating...")
        login_data = {
            "username": username,
            "password": password,
        }

        try:
            login_response = await client.post(
                "/api/v1/login",
                data=login_data,  # OAuth2PasswordRequestForm expects form data
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if login_response.status_code != 200:
                raise Exception(f"Login failed: {login_response.status_code} - {login_response.text}")

            tokens = login_response.json()
            setup_state["access_token"] = tokens["access_token"]
            print("   ✅ Authentication successful")
        except Exception as e:
            print(f"   ❌ Authentication failed: {e}")
            raise

        # Step 4: Create API key
        print("4. Creating API key...")
        headers = {"Authorization": f"Bearer {setup_state['access_token']}"}

        try:
            api_key_data = {"name": f"Load Test Key - {int(time.time())}"}
            api_key_response = await client.post("/api/v1/api_key/", json=api_key_data, headers=headers)

            if api_key_response.status_code != 200:
                raise Exception(f"API key creation failed: {api_key_response.status_code} - {api_key_response.text}")

            api_key_info = api_key_response.json()
            setup_state["api_key"] = api_key_info["api_key"]
            print(f"   ✅ API key created: {api_key_info['api_key'][:20]}...")
        except Exception as e:
            print(f"   ❌ API key creation failed: {e}")
            raise

        # Step 5: Select and load flow from API
        print("5. Selecting starter project flow...")

        # Flow selection logic
        selected_flow_name = None
        if interactive:
            selected_flow_name = await select_flow_interactive(host, setup_state["access_token"])
            if not selected_flow_name:
                print("No flow selected. Exiting.")
                sys.exit(0)
        elif flow_name:
            # Verify the flow exists in the API
            flows = await list_available_flows(host, setup_state["access_token"])
            for fname, name, _ in flows:
                if name.lower() == flow_name.lower():
                    selected_flow_name = name
                    break

            if not selected_flow_name:
                print(f"❌ Flow '{flow_name}' not found in starter projects!")
                print("Available flows:")
                for _, name, _ in flows:
                    print(f"  - {name}")
                sys.exit(1)
        else:
            # Default to Basic Prompting
            selected_flow_name = "Basic Prompting"
            print("   Using default flow: Basic Prompting")

        # Get flow data from API
        flow_data = await get_flow_data_by_name(host, setup_state["access_token"], selected_flow_name)
        if not flow_data:
            print(f"❌ Could not load flow data for '{selected_flow_name}'")
            sys.exit(1)

        setup_state["flow_name"] = flow_data.get("name", selected_flow_name)
        setup_state["flow_data"] = flow_data

        print(f"   ✅ Selected flow: {setup_state['flow_name']}")
        print(f"   Description: {flow_data.get('description', 'No description')}")

        # Step 6: Upload the selected flow
        print(f"6. Uploading flow: {setup_state['flow_name']}...")

        try:
            # Prepare flow data for upload
            # Remove the id to let Langflow generate a new one
            flow_upload_data = flow_data.copy()
            if "id" in flow_upload_data:
                del flow_upload_data["id"]

            # Ensure endpoint_name is unique and valid (only letters, numbers, hyphens, underscores)
            import re

            sanitized_name = re.sub(r"[^a-zA-Z0-9_-]", "_", setup_state["flow_name"].lower())
            flow_upload_data["endpoint_name"] = f"loadtest_{int(time.time())}_{sanitized_name}"

            flow_response = await client.post("/api/v1/flows/", json=flow_upload_data, headers=headers)

            if flow_response.status_code != 201:
                raise Exception(f"Flow upload failed: {flow_response.status_code} - {flow_response.text}")

            flow_info = flow_response.json()
            setup_state["flow_id"] = flow_info["id"]
            print("   ✅ Flow uploaded successfully")
            print(f"      Flow ID: {flow_info['id']}")
            print(f"      Endpoint: {flow_info.get('endpoint_name', 'N/A')}")
        except Exception as e:
            print(f"   ❌ Flow upload failed: {e}")
            raise

    return setup_state


def print_setup_results(setup_state: dict):
    """Print the setup results in a clear format."""
    print(f"\n{'=' * 80}")
    print("SETUP COMPLETE - LOAD TEST CREDENTIALS")
    print(f"{'=' * 80}")
    print(f"Host:        {setup_state['host']}")
    print(f"Username:    {setup_state['username']}")
    print(f"Password:    {setup_state['password']}")
    print(f"User ID:     {setup_state.get('user_id', 'N/A')}")
    print(f"JWT Token:   {setup_state['access_token'][:50]}..." if setup_state["access_token"] else "N/A")
    print(f"API Key:     {setup_state['api_key']}")
    print(f"Flow ID:     {setup_state['flow_id']}")
    print(f"Flow Name:   {setup_state['flow_name']}")
    print(f"{'=' * 80}")

    print("\n📋 COPY THESE COMMANDS TO RUN LOAD TESTS:")
    print(f"{'=' * 80}")

    # Environment variables for easy copy-paste
    print("# Set environment variables:")
    print(f"export LANGFLOW_HOST='{setup_state['host']}'")
    print(f"export API_KEY='{setup_state['api_key']}'")
    print(f"export FLOW_ID='{setup_state['flow_id']}'")
    print()

    # Direct locust commands
    print("# Run load test with web UI:")
    print(f"locust -f locustfile.py --host {setup_state['host']}")
    print()

    print("# Run headless load test (50 users, 2 minutes):")
    print(f"locust -f locustfile.py --host {setup_state['host']} --headless --users 50 --spawn-rate 5 --run-time 120s")
    print()

    print("# Run with load shape:")
    print(
        f"SHAPE=ramp100 locust -f locustfile.py --host {setup_state['host']} --headless --users 100 --spawn-rate 5 --run-time 180s"
    )
    print()

    print("# Or use the runner script:")
    print(
        f"python run_load_test.py --host {setup_state['host']} --no-start-langflow --headless --users 25 --duration 120"
    )
    print()

    print("# Generate HTML report:")
    print(
        f"python run_load_test.py --host {setup_state['host']} --no-start-langflow --headless --users 50 --duration 180 --html report.html"
    )

    print(f"\n{'=' * 80}")


def save_credentials(setup_state: dict, output_file: str):
    """Save credentials to a file for later use."""
    credentials = {
        "host": setup_state["host"],
        "api_key": setup_state["api_key"],
        "flow_id": setup_state["flow_id"],
        "flow_name": setup_state["flow_name"],
        "username": setup_state["username"],
        "password": setup_state["password"],
        "access_token": setup_state["access_token"],
        "created_at": time.time(),
    }

    try:
        with open(output_file, "w") as f:
            json.dump(credentials, f, indent=2)
        print(f"\n💾 Credentials saved to: {output_file}")
    except Exception as e:
        print(f"⚠️  Could not save credentials: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Set up Langflow load test environment with real starter project flows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive flow selection
  python setup_langflow_test.py --interactive

  # Use specific flow
  python setup_langflow_test.py --flow "Memory Chatbot"

  # List available flows
  python setup_langflow_test.py --list-flows

  # Setup with custom host
  python setup_langflow_test.py --host http://localhost:8000 --interactive

  # Save credentials to file
  python setup_langflow_test.py --interactive --save-credentials test_creds.json
        """,
    )

    parser.add_argument(
        "--host",
        default="http://localhost:7860",
        help="Langflow host URL (default: http://localhost:7860, use https:// for remote instances)",
    )
    parser.add_argument("--flow", help="Name of the starter project flow to use")
    parser.add_argument("--interactive", action="store_true", help="Interactive flow selection")
    parser.add_argument("--list-flows", action="store_true", help="List available starter project flows and exit")
    parser.add_argument("--save-credentials", metavar="FILE", help="Save credentials to a JSON file")

    args = parser.parse_args()

    # List flows and exit
    if args.list_flows:

        async def list_flows_only():
            try:
                import httpx
            except ImportError:
                print("❌ Missing dependency: httpx")
                print("Install with: pip install httpx")
                sys.exit(1)

            # Quick authentication to access the API
            username = "langflow"
            password = "langflow"

            async with httpx.AsyncClient(base_url=args.host, timeout=30.0) as client:
                # Health check
                try:
                    health_response = await client.get("/health")
                    if health_response.status_code != 200:
                        raise Exception(f"Langflow not available at {args.host}")
                except Exception as e:
                    print(f"❌ Cannot connect to Langflow at {args.host}: {e}")
                    sys.exit(1)

                # Login to get access token
                try:
                    login_data = {"username": username, "password": password}
                    login_response = await client.post(
                        "/api/v1/login",
                        data=login_data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )

                    if login_response.status_code != 200:
                        raise Exception(f"Authentication failed: {login_response.status_code}")

                    tokens = login_response.json()
                    access_token = tokens["access_token"]

                except Exception as e:
                    print(f"❌ Authentication failed: {e}")
                    print("Make sure Langflow is running with default credentials (langflow/langflow)")
                    sys.exit(1)

                # Get flows from API
                flows = await list_available_flows(args.host, access_token)
                if not flows:
                    print("❌ No starter project flows found!")
                    sys.exit(1)

                print(f"\n{'=' * 80}")
                print("AVAILABLE STARTER PROJECT FLOWS")
                print(f"{'=' * 80}")

                for flow_name, name, description in flows:
                    print(f"📄 {name}")
                    print(f"   Description: {description}")
                    print()

                print(f"Total: {len(flows)} flows available")

        asyncio.run(list_flows_only())
        sys.exit(0)

    # Validate arguments
    if not args.interactive and not args.flow:
        print("❌ Either --interactive or --flow must be specified")
        print("Use --help for more information")
        sys.exit(1)

    try:
        # Run the setup
        setup_state = asyncio.run(
            setup_langflow_environment(host=args.host, flow_name=args.flow, interactive=args.interactive)
        )

        # Print results
        print_setup_results(setup_state)

        # Save credentials if requested
        if args.save_credentials:
            save_credentials(setup_state, args.save_credentials)

        print("\n🚀 Environment setup complete! You can now run load tests.")

    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
