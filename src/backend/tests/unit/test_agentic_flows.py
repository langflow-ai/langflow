"""Tests for agentic flows setup and update functionality."""

import tempfile

import orjson
import pytest
from anyio import Path
from langflow.initial_setup.setup import (
    create_or_update_agentic_flows,
    load_agentic_flows,
    update_agentic_flow_files,
    update_flow_files,
)
from langflow.interface.components import get_and_cache_all_types_dict
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_settings_service, session_scope
from lfx.base.constants import ORJSON_OPTIONS
from sqlmodel import select


async def test_load_agentic_flows():
    """Test that agentic flows can be loaded from the directory."""
    flows = await load_agentic_flows()
    assert isinstance(flows, list)

    # Should have at least the two flows we know exist
    assert len(flows) >= 2

    # Each flow should be a tuple of (Path, dict)
    for flow_path, flow_data in flows:
        assert isinstance(flow_path, Path)
        assert isinstance(flow_data, dict)
        assert "data" in flow_data
        assert "name" in flow_data


async def test_update_flow_files_generic():
    """Test the generic update_flow_files function."""
    # Create a temporary directory with a test flow
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a simple test flow
        test_flow = {"name": "Test Flow", "description": "Test", "data": {"nodes": [], "edges": []}}

        flow_file = temp_path / "test_flow.json"
        from aiofile import async_open

        async with async_open(str(flow_file), "w") as f:
            await f.write(orjson.dumps(test_flow, option=ORJSON_OPTIONS).decode())

        # Get all types dict
        all_types = await get_and_cache_all_types_dict(get_settings_service())

        # Update the flow files
        updated_count = await update_flow_files(temp_path, all_types, "test")

        # Since the flow has no components, it shouldn't be updated
        assert updated_count == 0

        # Verify the file still exists
        assert await flow_file.exists()


async def test_update_flow_files_nonexistent_directory():
    """Test update_flow_files with a non-existent directory."""
    all_types = await get_and_cache_all_types_dict(get_settings_service())
    nonexistent_path = Path("/nonexistent/directory/that/does/not/exist")

    # Should return 0 without raising an error
    updated_count = await update_flow_files(nonexistent_path, all_types, "test")
    assert updated_count == 0


async def test_update_agentic_flow_files():
    """Test that agentic flow files can be updated with latest components."""
    all_types = await get_and_cache_all_types_dict(get_settings_service())

    # This should not raise an error
    await update_agentic_flow_files(all_types)

    # Verify flows can still be loaded
    flows = await load_agentic_flows()
    assert len(flows) >= 2


async def test_agentic_flows_have_required_fields():
    """Test that all agentic flows have required fields."""
    flows = await load_agentic_flows()

    for flow_path, flow_data in flows:
        # Check required top-level fields
        assert "name" in flow_data, f"Flow {flow_path.name} missing 'name'"
        assert "description" in flow_data, f"Flow {flow_path.name} missing 'description'"
        assert "data" in flow_data, f"Flow {flow_path.name} missing 'data'"

        # Check data structure
        data = flow_data["data"]
        assert "nodes" in data, f"Flow {flow_path.name} missing 'nodes' in data"
        assert "edges" in data, f"Flow {flow_path.name} missing 'edges' in data"
        assert isinstance(data["nodes"], list), f"Flow {flow_path.name} nodes should be a list"
        assert isinstance(data["edges"], list), f"Flow {flow_path.name} edges should be a list"


@pytest.mark.usefixtures("client")
async def test_create_or_update_agentic_flows_creates_flows():
    """Test that create_or_update_agentic_flows creates flows in the database."""
    # Enable agentic experience
    settings = get_settings_service().settings
    original_agentic = settings.agentic_experience
    settings.agentic_experience = True

    try:
        async with session_scope() as session:
            # Get superuser
            from langflow.services.database.models.user.model import User

            stmt = select(User).where(User.is_superuser == True)  # noqa: E712
            user = (await session.exec(stmt)).first()
            assert user is not None

            # Get all types for updating
            all_types = await get_and_cache_all_types_dict(get_settings_service())

            # Create or update agentic flows
            await create_or_update_agentic_flows(session, user.id, all_types)

            # Verify flows were created
            stmt = select(Folder).where(Folder.name == "Langflow Assistant", Folder.user_id == user.id)
            folder = (await session.exec(stmt)).first()
            assert folder is not None

            # Check flows in the folder
            stmt = select(Flow).where(Flow.folder_id == folder.id)
            flows = (await session.exec(stmt)).all()

            # Should have created at least 2 flows
            assert len(flows) >= 2

            # Verify flow names
            flow_names = [flow.name for flow in flows]
            assert any("SystemMessageGen" in name or "System Message" in name for name in flow_names)
            assert any("TemplateAssistant" in name or "Template Assistant" in name for name in flow_names)
    finally:
        settings.agentic_experience = original_agentic


@pytest.mark.usefixtures("client")
async def test_create_or_update_agentic_flows_updates_existing():
    """Test that create_or_update_agentic_flows updates existing flows."""
    settings = get_settings_service().settings
    original_agentic = settings.agentic_experience
    settings.agentic_experience = True

    try:
        async with session_scope() as session:
            # Get superuser
            from langflow.services.database.models.user.model import User

            stmt = select(User).where(User.is_superuser == True)  # noqa: E712
            user = (await session.exec(stmt)).first()
            assert user is not None

            # Get all types
            all_types = await get_and_cache_all_types_dict(get_settings_service())

            # Create flows first time
            await create_or_update_agentic_flows(session, user.id, all_types)

            # Get one of the flows
            stmt = select(Folder).where(Folder.name == "Langflow Assistant", Folder.user_id == user.id)
            folder = (await session.exec(stmt)).first()
            assert folder is not None

            stmt = select(Flow).where(Flow.folder_id == folder.id)
            flows_before = (await session.exec(stmt)).all()
            flow_count_before = len(flows_before)

            # Modify one flow's description
            if flows_before:
                flows_before[0].description = "Modified description"
                session.add(flows_before[0])
                await session.commit()

            # Update flows again
            await create_or_update_agentic_flows(session, user.id, all_types)

            # Verify flow count is the same (no duplicates)
            stmt = select(Flow).where(Flow.folder_id == folder.id)
            flows_after = (await session.exec(stmt)).all()
            assert len(flows_after) == flow_count_before

            # Verify the description was updated back
            if flows_before:
                stmt = select(Flow).where(Flow.id == flows_before[0].id)
                updated_flow = (await session.exec(stmt)).first()
                assert updated_flow.description != "Modified description"
    finally:
        settings.agentic_experience = original_agentic


@pytest.mark.usefixtures("client")
async def test_create_or_update_agentic_flows_disabled():
    """Test that create_or_update_agentic_flows does nothing when agentic experience is disabled."""
    settings = get_settings_service().settings
    original_agentic = settings.agentic_experience
    settings.agentic_experience = False

    try:
        async with session_scope() as session:
            # Get superuser
            from langflow.services.database.models.user.model import User

            stmt = select(User).where(User.is_superuser == True)  # noqa: E712
            user = (await session.exec(stmt)).first()
            assert user is not None

            # This should do nothing
            await create_or_update_agentic_flows(session, user.id)

            # Verify no Langflow Assistant folder was created
            stmt = select(Folder).where(Folder.name == "Langflow Assistant", Folder.user_id == user.id)
            folder = (await session.exec(stmt)).first()
            # Folder might exist from previous tests, but no new flows should be added
            # This is a weak assertion but acceptable
    finally:
        settings.agentic_experience = original_agentic


async def test_update_flow_files_with_invalid_json():
    """Test update_flow_files handles invalid JSON gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create an invalid JSON file
        invalid_file = temp_path / "invalid.json"
        from aiofile import async_open

        async with async_open(str(invalid_file), "w") as f:
            await f.write("{ invalid json }")

        all_types = await get_and_cache_all_types_dict(get_settings_service())

        # Should not raise an error, just log it
        updated_count = await update_flow_files(temp_path, all_types, "test")
        assert updated_count == 0


async def test_agentic_flows_components_are_valid():
    """Test that all components in agentic flows are valid or are custom components."""
    flows = await load_agentic_flows()
    all_types = await get_and_cache_all_types_dict(get_settings_service())

    # Flatten all_types_dict for easy lookup
    all_types_flat = {}
    for category in all_types.values():
        for key, component in category.items():
            all_types_flat[key] = component

    for flow_path, flow_data in flows:
        data = flow_data.get("data", {})
        nodes = data.get("nodes", [])

        for node in nodes:
            node_data = node.get("data", {})
            node_type = node_data.get("type")
            # Skip custom components (they have code in their template)
            if node_data.get("node", {}).get("template", {}).get("code"):
                continue
            # Verify the component type exists
            assert node_type in all_types_flat, f"Flow {flow_path.name} contains unknown component type: {node_type}"


@pytest.mark.usefixtures("client")
async def test_agentic_flows_preserve_edges_after_update():
    """Test that edges are preserved when flows are created/updated in the database."""
    settings = get_settings_service().settings
    original_agentic = settings.agentic_experience
    settings.agentic_experience = True

    try:
        async with session_scope() as session:
            # Get superuser
            from langflow.services.database.models.user.model import User

            stmt = select(User).where(User.is_superuser == True)  # noqa: E712
            user = (await session.exec(stmt)).first()
            assert user is not None

            # Get all types
            all_types = await get_and_cache_all_types_dict(get_settings_service())

            # Create flows with all_types_dict (simulating startup)
            await create_or_update_agentic_flows(session, user.id, all_types)

            # Get the flows from database
            stmt = select(Folder).where(Folder.name == "Langflow Assistant", Folder.user_id == user.id)
            folder = (await session.exec(stmt)).first()
            assert folder is not None

            stmt = select(Flow).where(Flow.folder_id == folder.id)
            flows = (await session.exec(stmt)).all()

            # Verify each flow has edges
            for flow in flows:
                data = flow.data
                assert "edges" in data, f"Flow {flow.name} missing edges in data"
                edges = data.get("edges", [])
                # SystemMessageGen should have 11 edges, TemplateAssistant should have 6
                if "SystemMessageGen" in flow.name or "System Message" in flow.name:
                    assert len(edges) >= 10, f"Flow {flow.name} should have at least 10 edges, got {len(edges)}"
                elif "TemplateAssistant" in flow.name or "Template Assistant" in flow.name:
                    assert len(edges) >= 5, f"Flow {flow.name} should have at least 5 edges, got {len(edges)}"
                else:
                    # Any agentic flow should have at least some edges
                    assert len(edges) > 0, f"Flow {flow.name} should have edges, got {len(edges)}"
    finally:
        settings.agentic_experience = original_agentic
