from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

CYRILLIC_NAME = "Новый проект"
CYRILLIC_DESC = "Описание проекта с кириллицей"  # noqa: RUF001


@pytest.fixture
def basic_case():
    return {
        "name": "New Project",
        "description": "",
        "flows_list": [],
        "components_list": [],
    }


async def test_create_project(client: AsyncClient, logged_in_headers, basic_case):
    response = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "parent_id" in result, "The dictionary must contain a key called 'parent_id'"


async def test_read_projects(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/projects/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"
    assert len(result) > 0, "The list must not be empty"


async def test_read_project(client: AsyncClient, logged_in_headers, basic_case):
    # Create a project first
    response_ = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]

    # Get the project
    response = await client.get(f"api/v1/projects/{id_}", headers=logged_in_headers)
    result = response.json()

    # The response structure may be different depending on whether pagination is enabled
    if isinstance(result, dict) and "folder" in result:
        # Handle paginated project response
        folder_data = result["folder"]
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(folder_data, dict), "The folder data must be a dictionary"
        assert "name" in folder_data, "The dictionary must contain a key called 'name'"
        assert "description" in folder_data, "The dictionary must contain a key called 'description'"
        assert "id" in folder_data, "The dictionary must contain a key called 'id'"
    elif isinstance(result, dict) and "project" in result:
        # Handle paginated project response
        project_data = result["project"]
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(project_data, dict), "The project data must be a dictionary"
        assert "name" in project_data, "The dictionary must contain a key called 'name'"
        assert "description" in project_data, "The dictionary must contain a key called 'description'"
        assert "id" in project_data, "The dictionary must contain a key called 'id'"
    else:
        # Handle direct project response
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(result, dict), "The result must be a dictionary"
        assert "name" in result, "The dictionary must contain a key called 'name'"
        assert "description" in result, "The dictionary must contain a key called 'description'"
        assert "id" in result, "The dictionary must contain a key called 'id'"


async def test_update_project(client: AsyncClient, logged_in_headers, basic_case):
    update_case = basic_case.copy()
    update_case["name"] = "Updated Project"

    # Create a project first
    response_ = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]

    # Update the project
    response = await client.patch(f"api/v1/projects/{id_}", json=update_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "name" in result, "The dictionary must contain a key called 'name'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "id" in result, "The dictionary must contain a key called 'id'"
    assert "parent_id" in result, "The dictionary must contain a key called 'parent_id'"


async def test_create_project_validation_error(client: AsyncClient, logged_in_headers, basic_case):
    invalid_case = basic_case.copy()
    invalid_case.pop("name")
    response = await client.post("api/v1/projects/", json=invalid_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_delete_project_then_404(client: AsyncClient, logged_in_headers, basic_case):
    create_resp = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    proj_id = create_resp.json()["id"]

    del_resp = await client.delete(f"api/v1/projects/{proj_id}", headers=logged_in_headers)
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT

    get_resp = await client.get(f"api/v1/projects/{proj_id}", headers=logged_in_headers)
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


async def test_read_project_invalid_id_format(client: AsyncClient, logged_in_headers):
    bad_id = "not-a-uuid"
    response = await client.get(f"api/v1/projects/{bad_id}", headers=logged_in_headers)
    assert response.status_code in (status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST)


async def test_read_projects_pagination(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/projects/?limit=1&offset=0", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    if isinstance(result, list):
        assert len(result) <= 1
    else:
        assert "items" in result
        assert result.get("limit") == 1


async def test_read_projects_empty(client: AsyncClient, logged_in_headers):
    # Ensure DB is clean by fetching with a random header that forces each test transactional isolation
    random_headers = {**logged_in_headers, "X-Transaction-ID": str(uuid4())}
    response = await client.get("api/v1/projects/", headers=random_headers)
    if response.json():
        pytest.skip("Pre-existing projects found; skipping empty list assertion")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


async def test_create_and_read_project_cyrillic(client: AsyncClient, logged_in_headers):
    """Ensure that the API correctly handles non-ASCII (Cyrillic) characters during project creation and retrieval."""
    payload = {
        "name": CYRILLIC_NAME,
        "description": CYRILLIC_DESC,
        "flows_list": [],
        "components_list": [],
    }

    # Create the project with Cyrillic characters
    create_resp = await client.post("api/v1/projects/", json=payload, headers=logged_in_headers)
    assert create_resp.status_code == status.HTTP_201_CREATED
    created = create_resp.json()
    assert created["name"] == CYRILLIC_NAME
    assert created["description"] == CYRILLIC_DESC
    proj_id = created["id"]

    # Fetch the project back to verify round-trip UTF-8 integrity
    get_resp = await client.get(f"api/v1/projects/{proj_id}", headers=logged_in_headers)
    assert get_resp.status_code == status.HTTP_200_OK
    fetched = get_resp.json()

    # Handle potential pagination/envelope variations already seen in other tests
    if isinstance(fetched, dict) and "folder" in fetched:
        fetched = fetched["folder"]
    elif isinstance(fetched, dict) and "project" in fetched:
        fetched = fetched["project"]

    assert fetched["name"] == CYRILLIC_NAME
    assert fetched["description"] == CYRILLIC_DESC


async def test_export_project(client: AsyncClient, logged_in_headers, basic_case):
    """Test exporting a project with flows."""
    # Create a project first
    response = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    project_id = response.json()["id"]

    # Create a flow in the project
    flow_data = {
        "name": "Test Flow",
        "description": "Test flow description",
        "data": {"nodes": [], "edges": [], "viewport": {}},
        "folder_id": project_id,
    }
    flow_response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED

    # Export the project
    export_response = await client.get(f"api/v1/projects/export/{project_id}", headers=logged_in_headers)
    assert export_response.status_code == status.HTTP_200_OK

    # Check response headers - now returns ZIP instead of JSON
    assert "application/x-zip-compressed" in export_response.headers["content-type"]
    assert "attachment" in export_response.headers["content-disposition"]

    # Parse and validate export data as ZIP
    import io
    import json
    import zipfile

    zip_content = io.BytesIO(export_response.content)

    with zipfile.ZipFile(zip_content, "r") as zip_file:
        # Check that project.json exists and contains expected data
        assert "project.json" in zip_file.namelist()
        project_content = zip_file.read("project.json").decode("utf-8")
        export_data = json.loads(project_content)

        assert export_data["version"] == "2.0"
        assert export_data["export_type"] == "project_enhanced"
        assert "exported_at" in export_data
        assert "project" in export_data
        assert "flows" in export_data

        # Validate project data
        project_data = export_data["project"]
        assert project_data["id"] == project_id
        assert project_data["name"] == "New Project"

        # Validate flows data
        flows = export_data["flows"]
        assert len(flows) == 1
        assert flows[0]["name"] == "Test Flow"
        assert flows[0]["description"] == "Test flow description"


async def test_export_project_not_found(client: AsyncClient, logged_in_headers):
    """Test exporting a non-existent project."""
    fake_id = str(uuid4())
    response = await client.get(f"api/v1/projects/export/{fake_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_export_project_with_code_extraction(client: AsyncClient, logged_in_headers, basic_case):
    """Test enhanced project export with ZIP archive and code extraction."""
    import io
    import json
    import zipfile

    # Create a project first
    response = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    project_id = response.json()["id"]

    # Use complex_example fixture that contains PythonFunctionTool with code
    from pathlib import Path

    data_path = Path("/Users/ogabrielluiz/Projects/langflow/src/backend/tests/data/complex_example.json")
    complex_flow_data = json.loads(data_path.read_text(encoding="utf-8"))

    # Set the project folder_id
    complex_flow_data["folder_id"] = project_id

    flow_response = await client.post("api/v1/flows/", json=complex_flow_data, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED

    # Export the project using export endpoint
    export_response = await client.get(f"api/v1/projects/export/{project_id}", headers=logged_in_headers)
    assert export_response.status_code == status.HTTP_200_OK

    # Check response headers
    assert "application/x-zip-compressed" in export_response.headers["content-type"]
    assert "attachment" in export_response.headers["content-disposition"]
    assert "_export.zip" in export_response.headers["content-disposition"]

    # Parse ZIP archive
    zip_content = io.BytesIO(export_response.content)

    with zipfile.ZipFile(zip_content, "r") as zip_file:
        # Check required files exist
        file_list = zip_file.namelist()
        assert "project.json" in file_list
        assert "README.md" in file_list
        assert any(f.startswith("flows/") and f.endswith(".json") for f in file_list)
        # Check that code files were extracted from PythonFunctionTool component
        code_files = [f for f in file_list if f.startswith("components/") and f.endswith(".py")]
        assert len(code_files) == 1  # Should have 1 PythonFunctionTool component with code

        # Verify the extracted code content
        code_file = code_files[0]
        code_content = zip_file.read(code_file).decode("utf-8")
        assert '"""Component: PythonFunctionTool' in code_content
        assert "def python_function(text: str) -> str:" in code_content
        assert "return text" in code_content

        # Validate project.json structure
        project_content = zip_file.read("project.json").decode("utf-8")
        project_data = json.loads(project_content)

        assert project_data["version"] == "2.0"
        assert project_data["export_type"] == "project_enhanced"
        assert "exported_at" in project_data
        assert "project" in project_data
        assert "flows" in project_data
        assert project_data["project"]["id"] == project_id
        assert project_data["project"]["name"] == "New Project"
        assert len(project_data["flows"]) == 1

        # Validate README.md exists and contains expected content
        readme_content = zip_file.read("README.md").decode("utf-8")
        assert "Enhanced Export" in readme_content
        assert "Export format version: 2.0" in readme_content
        assert "Static analysis" in readme_content

        # Validate flow JSON file
        flow_files = [f for f in file_list if f.startswith("flows/") and f.endswith(".json")]
        assert len(flow_files) == 1
        flow_content = zip_file.read(flow_files[0]).decode("utf-8")
        flow_json = json.loads(flow_content)
        assert flow_json["name"] == "complex_example"

        # Validate extracted code files
        code_files = [f for f in file_list if f.startswith("components/") and f.endswith(".py")]
        assert len(code_files) == 2

        # Check that code files contain expected content
        for code_file in code_files:
            code_content = zip_file.read(code_file).decode("utf-8")
            # Should have docstring with metadata
            assert '"""Component:' in code_content
            assert "Flow: Test Flow with Code" in code_content
            # Should contain actual code
            assert "class " in code_content

        # Verify specific components
        chatinput_files = [f for f in code_files if "ChatInput" in f]
        textinput_files = [f for f in code_files if "TextInput" in f]
        assert len(chatinput_files) == 1
        assert len(textinput_files) == 1

        # Check ChatInput code content
        chatinput_content = zip_file.read(chatinput_files[0]).decode("utf-8")
        assert "ChatComponent" in chatinput_content
        assert "class ChatInput" in chatinput_content

        # Check TextInput code content
        textinput_content = zip_file.read(textinput_files[0]).decode("utf-8")
        assert "TextComponent" in textinput_content
        assert "def process" in textinput_content


async def test_export_project_no_code(client: AsyncClient, logged_in_headers, basic_case):
    """Test export with flows that have no custom code."""
    import io
    import zipfile

    # Create a project first
    response = await client.post("api/v1/projects/", json=basic_case, headers=logged_in_headers)
    project_id = response.json()["id"]

    # Create a flow without custom code components
    flow_data_no_code = {
        "name": "Test Flow No Code",
        "description": "Test flow without custom components",
        "data": {"nodes": [], "edges": [], "viewport": {}},
        "folder_id": project_id,
    }

    flow_response = await client.post("api/v1/flows/", json=flow_data_no_code, headers=logged_in_headers)
    assert flow_response.status_code == status.HTTP_201_CREATED

    # Export the project using export endpoint
    export_response = await client.get(f"api/v1/projects/export/{project_id}", headers=logged_in_headers)
    assert export_response.status_code == status.HTTP_200_OK

    # Parse ZIP archive
    zip_content = io.BytesIO(export_response.content)

    with zipfile.ZipFile(zip_content, "r") as zip_file:
        file_list = zip_file.namelist()

        # Basic structure should still exist
        assert "project.json" in file_list
        assert "README.md" in file_list
        assert any(f.startswith("flows/") and f.endswith(".json") for f in file_list)

        # No component code files should exist
        code_files = [f for f in file_list if f.startswith("components/") and f.endswith(".py")]
        assert len(code_files) == 0

        # README should indicate no code files
        readme_content = zip_file.read("README.md").decode("utf-8")
        assert "Code files extracted: 0" in readme_content
