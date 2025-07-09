import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_duplicate_flow_name_basic(client: AsyncClient, logged_in_headers):
    """Test that duplicate flow names get numbered correctly."""
    base_flow = {
        "name": "Test Flow",
        "description": "Test flow description",
        "data": {},
        "is_component": False,
    }
    
    # Create first flow
    response1 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response1.status_code == status.HTTP_201_CREATED
    assert response1.json()["name"] == "Test Flow"
    
    # Create second flow with same name - should become "Test Flow (1)"
    response2 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response2.status_code == status.HTTP_201_CREATED
    assert response2.json()["name"] == "Test Flow (1)"
    
    # Create third flow with same name - should become "Test Flow (2)"
    response3 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response3.status_code == status.HTTP_201_CREATED
    assert response3.json()["name"] == "Test Flow (2)"


@pytest.mark.asyncio
async def test_duplicate_flow_name_with_numbers_in_original(client: AsyncClient, logged_in_headers):
    """Test duplication of flows with numbers in their original name."""
    base_flow = {
        "name": "Untitled document (7)",
        "description": "Test flow description",
        "data": {},
        "is_component": False,
    }
    
    # Create first flow
    response1 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response1.status_code == status.HTTP_201_CREATED
    assert response1.json()["name"] == "Untitled document (7)"
    
    # Create second flow with same name - should become "Untitled document (7) (1)"
    response2 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response2.status_code == status.HTTP_201_CREATED
    assert response2.json()["name"] == "Untitled document (7) (1)"
    
    # Create third flow with same name - should become "Untitled document (7) (2)"
    response3 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response3.status_code == status.HTTP_201_CREATED
    assert response3.json()["name"] == "Untitled document (7) (2)"


@pytest.mark.asyncio
async def test_duplicate_flow_name_with_non_numeric_suffixes(client: AsyncClient, logged_in_headers):
    """Test that non-numeric suffixes don't interfere with numbering."""
    base_flow = {
        "name": "My Flow",
        "description": "Test flow description", 
        "data": {},
        "is_component": False,
    }
    
    # Create first flow
    response1 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response1.status_code == status.HTTP_201_CREATED
    assert response1.json()["name"] == "My Flow"
    
    # Create flow with non-numeric suffix
    backup_flow = base_flow.copy()
    backup_flow["name"] = "My Flow (Backup)"
    response2 = await client.post("api/v1/flows/", json=backup_flow, headers=logged_in_headers)
    assert response2.status_code == status.HTTP_201_CREATED
    assert response2.json()["name"] == "My Flow (Backup)"
    
    # Create another flow with original name - should become "My Flow (1)"
    # because "My Flow (Backup)" doesn't match the numeric pattern
    response3 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response3.status_code == status.HTTP_201_CREATED
    assert response3.json()["name"] == "My Flow (1)"


@pytest.mark.asyncio
async def test_duplicate_flow_name_gaps_in_numbering(client: AsyncClient, logged_in_headers):
    """Test that gaps in numbering are handled correctly (uses max + 1)."""
    base_flow = {
        "name": "Gapped Flow",
        "description": "Test flow description",
        "data": {},
        "is_component": False,
    }
    
    # Create original flow
    response1 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response1.status_code == status.HTTP_201_CREATED
    assert response1.json()["name"] == "Gapped Flow"
    
    # Create numbered flows with gaps
    numbered_flows = [
        "Gapped Flow (1)",
        "Gapped Flow (5)",  # Gap: 2, 3, 4 missing
        "Gapped Flow (7)",  # Gap: 6 missing
    ]
    
    for flow_name in numbered_flows:
        numbered_flow = base_flow.copy()
        numbered_flow["name"] = flow_name
        response = await client.post("api/v1/flows/", json=numbered_flow, headers=logged_in_headers)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == flow_name
    
    # Create another duplicate - should use max(1,5,7) + 1 = 8
    response_final = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response_final.status_code == status.HTTP_201_CREATED
    assert response_final.json()["name"] == "Gapped Flow (8)"


@pytest.mark.asyncio
async def test_duplicate_flow_name_special_characters(client: AsyncClient, logged_in_headers):
    """Test duplication with special characters in flow names."""
    base_flow = {
        "name": "Flow-with_special@chars!",
        "description": "Test flow description",
        "data": {},
        "is_component": False,
    }
    
    # Create first flow
    response1 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response1.status_code == status.HTTP_201_CREATED
    assert response1.json()["name"] == "Flow-with_special@chars!"
    
    # Create duplicate - should properly escape special characters in regex
    response2 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response2.status_code == status.HTTP_201_CREATED
    assert response2.json()["name"] == "Flow-with_special@chars! (1)"


@pytest.mark.asyncio
async def test_duplicate_flow_name_regex_patterns(client: AsyncClient, logged_in_headers):
    """Test that flow names containing regex special characters work correctly."""
    base_flow = {
        "name": "Flow (.*) [test]",
        "description": "Test flow description",
        "data": {},
        "is_component": False,
    }
    
    # Create first flow
    response1 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response1.status_code == status.HTTP_201_CREATED
    assert response1.json()["name"] == "Flow (.*) [test]"
    
    # Create duplicate
    response2 = await client.post("api/v1/flows/", json=base_flow, headers=logged_in_headers)
    assert response2.status_code == status.HTTP_201_CREATED
    assert response2.json()["name"] == "Flow (.*) [test] (1)"




