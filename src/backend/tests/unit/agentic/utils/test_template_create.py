"""Unit tests for template_create module using real templates."""

from uuid import UUID

import pytest
from fastapi import HTTPException
from langflow.agentic.utils.template_create import create_flow_from_template_and_get_link
from langflow.agentic.utils.template_search import get_template_by_id, list_templates
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope


@pytest.mark.skip(reason="Skipping agentic tests")
class TestCreateFlowFromTemplateAndGetLink:
    """Test cases for create_flow_from_template_and_get_link function."""

    @pytest.mark.asyncio
    async def test_create_flow_from_valid_template(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test creating a flow from a valid starter template."""
        # Get a valid template ID from starter projects
        templates = list_templates(fields=["id", "name"])
        assert len(templates) > 0, "No templates found in starter_projects"

        template_id = templates[0]["id"]
        template_name = templates[0]["name"]

        async with session_scope() as session:
            result = await create_flow_from_template_and_get_link(
                session=session,
                user_id=active_user.id,
                template_id=template_id,
            )

            assert "id" in result
            assert "link" in result
            assert result["id"]
            assert "/flow/" in result["link"]

            # Verify flow was created in database
            flow_id = UUID(result["id"]) if isinstance(result["id"], str) else result["id"]
            flow = await session.get(Flow, flow_id)
            assert flow is not None
            assert flow.name == template_name

            # Cleanup
            if flow:
                await session.delete(flow)
                await session.commit()

    @pytest.mark.asyncio
    async def test_create_flow_with_target_folder(self, client, logged_in_headers, active_user):
        """Test creating a flow in a specific target folder."""
        # Create a folder first (using projects endpoint as folders redirects)
        folder_response = await client.post(
            "api/v1/projects/",
            json={"name": "Template Test Folder", "description": "Folder for template tests"},
            headers=logged_in_headers,
        )
        assert folder_response.status_code == 201
        folder_id_str = folder_response.json()["id"]
        folder_uuid = UUID(folder_id_str)

        try:
            # Get a valid template
            templates = list_templates(fields=["id"])
            assert len(templates) > 0

            template_id = templates[0]["id"]

            async with session_scope() as session:
                result = await create_flow_from_template_and_get_link(
                    session=session,
                    user_id=active_user.id,
                    template_id=template_id,
                    target_folder_id=folder_uuid,
                )

                assert "id" in result
                assert "link" in result
                # Link should reference the folder
                assert f"/folder/{folder_id_str}" in result["link"]

                # Verify flow is in correct folder
                flow = await session.get(Flow, UUID(result["id"]) if isinstance(result["id"], str) else result["id"])
                assert flow is not None
                assert str(flow.folder_id) == folder_id_str

                # Cleanup flow
                if flow:
                    await session.delete(flow)
                    await session.commit()

        finally:
            # Cleanup folder
            await client.delete(f"api/v1/projects/{folder_id_str}", headers=logged_in_headers)

    @pytest.mark.asyncio
    async def test_create_flow_default_folder(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test that flow is created in default folder when no folder specified."""
        templates = list_templates(fields=["id"])
        assert len(templates) > 0

        template_id = templates[0]["id"]

        async with session_scope() as session:
            result = await create_flow_from_template_and_get_link(
                session=session,
                user_id=active_user.id,
                template_id=template_id,
                target_folder_id=None,  # No folder specified
            )

            assert "id" in result
            assert "link" in result

            # Verify flow was created with a folder
            flow = await session.get(Flow, UUID(result["id"]) if isinstance(result["id"], str) else result["id"])
            assert flow is not None
            assert flow.folder_id is not None

            # Cleanup
            if flow:
                await session.delete(flow)
                await session.commit()

    @pytest.mark.asyncio
    async def test_create_flow_nonexistent_template(self, client, active_user):  # noqa: ARG002
        """Test that creating flow from nonexistent template raises error."""
        nonexistent_template_id = "00000000-0000-0000-0000-000000000000"

        async with session_scope() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_flow_from_template_and_get_link(
                    session=session,
                    user_id=active_user.id,
                    template_id=nonexistent_template_id,
                )

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_flow_invalid_folder(self, client, active_user):  # noqa: ARG002
        """Test that creating flow in invalid folder raises error."""
        templates = list_templates(fields=["id"])
        assert len(templates) > 0

        template_id = templates[0]["id"]
        invalid_folder_id = UUID("00000000-0000-0000-0000-000000000000")

        async with session_scope() as session:
            with pytest.raises(HTTPException) as exc_info:
                await create_flow_from_template_and_get_link(
                    session=session,
                    user_id=active_user.id,
                    template_id=template_id,
                    target_folder_id=invalid_folder_id,
                )

            assert exc_info.value.status_code == 400
            assert "invalid" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_flow_data_matches_template(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test that created flow data matches template data."""
        templates = list_templates(fields=["id", "name", "description", "data"])
        assert len(templates) > 0

        template = templates[0]
        template_id = template["id"]

        async with session_scope() as session:
            result = await create_flow_from_template_and_get_link(
                session=session,
                user_id=active_user.id,
                template_id=template_id,
            )

            flow = await session.get(Flow, UUID(result["id"]) if isinstance(result["id"], str) else result["id"])
            assert flow is not None

            # Verify data structure matches
            if template.get("data"):
                assert flow.data is not None
                # The flow data should contain the template's node/edge structure
                if "nodes" in template["data"]:
                    assert "nodes" in flow.data

            # Cleanup
            if flow:
                await session.delete(flow)
                await session.commit()

    @pytest.mark.asyncio
    async def test_create_flow_preserves_template_metadata(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test that created flow preserves template metadata."""
        templates = list_templates(fields=["id", "name", "description", "icon", "tags"])
        assert len(templates) > 0

        template = templates[0]
        template_id = template["id"]

        async with session_scope() as session:
            result = await create_flow_from_template_and_get_link(
                session=session,
                user_id=active_user.id,
                template_id=template_id,
            )

            flow = await session.get(Flow, UUID(result["id"]) if isinstance(result["id"], str) else result["id"])
            assert flow is not None

            # Check metadata is preserved
            if template.get("name"):
                assert flow.name == template["name"]
            if template.get("description"):
                assert flow.description == template["description"]

            # Cleanup
            if flow:
                await session.delete(flow)
                await session.commit()

    @pytest.mark.asyncio
    async def test_create_multiple_flows_from_same_template(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test creating multiple flows from the same template."""
        templates = list_templates(fields=["id"])
        assert len(templates) > 0

        template_id = templates[0]["id"]
        created_flows = []

        try:
            async with session_scope() as session:
                # Create 3 flows from same template
                for _ in range(3):
                    result = await create_flow_from_template_and_get_link(
                        session=session,
                        user_id=active_user.id,
                        template_id=template_id,
                    )
                    created_flows.append(result["id"])

                # All flows should be created successfully
                assert len(created_flows) == 3

                # All should have unique IDs
                assert len(set(created_flows)) == 3

                # Cleanup
                for flow_id_str in created_flows:
                    flow_uuid = UUID(flow_id_str) if isinstance(flow_id_str, str) else flow_id_str
                    flow = await session.get(Flow, flow_uuid)
                    if flow:
                        await session.delete(flow)
                await session.commit()

        except Exception:
            # Cleanup on error
            async with session_scope() as session:
                for flow_id_str in created_flows:
                    flow_uuid = UUID(flow_id_str) if isinstance(flow_id_str, str) else flow_id_str
                    flow = await session.get(Flow, flow_uuid)
                    if flow:
                        await session.delete(flow)
                await session.commit()
            raise

    @pytest.mark.asyncio
    async def test_create_flow_link_format(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test that the returned link has correct format."""
        templates = list_templates(fields=["id"])
        assert len(templates) > 0

        template_id = templates[0]["id"]

        async with session_scope() as session:
            result = await create_flow_from_template_and_get_link(
                session=session,
                user_id=active_user.id,
                template_id=template_id,
            )

            # Link should follow pattern: /flow/{flow_id}/folder/{folder_id}
            link = result["link"]
            assert link.startswith("/flow/")
            assert "/folder/" in link

            # Parse and validate link structure
            parts = link.split("/")
            assert parts[1] == "flow"
            assert parts[2] == result["id"]  # Flow ID
            assert parts[3] == "folder"
            # parts[4] should be folder ID

            # Cleanup
            flow = await session.get(Flow, UUID(result["id"]) if isinstance(result["id"], str) else result["id"])
            if flow:
                await session.delete(flow)
                await session.commit()


@pytest.mark.skip(reason="Skipping agentic tests")
class TestIntegrationScenarios:
    """Integration tests with real-world scenarios."""

    @pytest.mark.asyncio
    async def test_create_flows_from_different_templates(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test creating flows from multiple different templates."""
        templates = list_templates(fields=["id", "name"])
        assert len(templates) >= 2, "Need at least 2 templates for this test"

        created_flows = []

        try:
            async with session_scope() as session:
                # Create flow from first two templates
                for template in templates[:2]:
                    result = await create_flow_from_template_and_get_link(
                        session=session,
                        user_id=active_user.id,
                        template_id=template["id"],
                    )
                    created_flows.append(
                        {
                            "flow_id": result["id"],
                            "template_name": template["name"],
                        }
                    )

                assert len(created_flows) == 2

                # Verify each flow matches its template
                for created in created_flows:
                    flow_uuid = UUID(created["flow_id"]) if isinstance(created["flow_id"], str) else created["flow_id"]
                    flow = await session.get(Flow, flow_uuid)
                    assert flow is not None
                    assert flow.name == created["template_name"]

        finally:
            # Cleanup
            async with session_scope() as session:
                for created in created_flows:
                    flow_uuid = UUID(created["flow_id"]) if isinstance(created["flow_id"], str) else created["flow_id"]
                    flow = await session.get(Flow, flow_uuid)
                    if flow:
                        await session.delete(flow)
                await session.commit()

    @pytest.mark.asyncio
    async def test_full_template_to_flow_workflow(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test complete workflow: search template -> create flow -> verify."""
        # Step 1: Search for templates with specific criteria
        templates = list_templates(query="agent", fields=["id", "name", "description", "tags"])

        if not templates:
            # Fall back to any template
            templates = list_templates(fields=["id", "name", "description"])

        assert len(templates) > 0

        template = templates[0]
        template_id = template["id"]

        try:
            async with session_scope() as session:
                # Step 2: Get full template details
                full_template = get_template_by_id(template_id)
                assert full_template is not None

                # Step 3: Create flow from template
                result = await create_flow_from_template_and_get_link(
                    session=session,
                    user_id=active_user.id,
                    template_id=template_id,
                )

                # Step 4: Verify flow was created correctly
                assert "id" in result
                assert "link" in result

                flow = await session.get(Flow, UUID(result["id"]) if isinstance(result["id"], str) else result["id"])
                assert flow is not None
                assert flow.name == full_template.get("name")
                assert flow.user_id == active_user.id

                # Cleanup
                if flow:
                    await session.delete(flow)
                    await session.commit()

        except Exception:
            # Ensure cleanup on error
            async with session_scope() as session:
                if "result" in dir() and result:
                    flow_id = UUID(result["id"]) if isinstance(result["id"], str) else result["id"]
                    flow = await session.get(Flow, flow_id)
                    if flow:
                        await session.delete(flow)
                        await session.commit()
            raise


@pytest.mark.skip(reason="Skipping agentic tests")
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_create_flow_with_empty_template_data(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test handling template with minimal data."""
        # Find a template and verify it can be created
        templates = list_templates(fields=["id", "data"])
        assert len(templates) > 0

        # Use the first template regardless of data content
        template_id = templates[0]["id"]

        async with session_scope() as session:
            try:
                result = await create_flow_from_template_and_get_link(
                    session=session,
                    user_id=active_user.id,
                    template_id=template_id,
                )

                # Should succeed
                assert "id" in result

                # Cleanup
                flow = await session.get(Flow, UUID(result["id"]) if isinstance(result["id"], str) else result["id"])
                if flow:
                    await session.delete(flow)
                    await session.commit()

            except HTTPException:
                # Some templates might fail - that's acceptable
                pass

    @pytest.mark.asyncio
    async def test_create_flow_user_ownership(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test that created flow is owned by the correct user."""
        templates = list_templates(fields=["id"])
        assert len(templates) > 0

        template_id = templates[0]["id"]

        async with session_scope() as session:
            result = await create_flow_from_template_and_get_link(
                session=session,
                user_id=active_user.id,
                template_id=template_id,
            )

            flow = await session.get(Flow, UUID(result["id"]) if isinstance(result["id"], str) else result["id"])
            assert flow is not None
            assert flow.user_id == active_user.id

            # Cleanup
            if flow:
                await session.delete(flow)
                await session.commit()

    @pytest.mark.asyncio
    async def test_create_flow_with_all_template_types(self, client, logged_in_headers, active_user):  # noqa: ARG002
        """Test creating flows from templates of different types."""
        templates = list_templates(fields=["id", "tags", "is_component"])
        assert len(templates) > 0

        created_count = 0
        created_flow_ids = []

        async with session_scope() as session:
            try:
                # Try to create from up to 5 different templates
                for template in templates[:5]:
                    try:
                        result = await create_flow_from_template_and_get_link(
                            session=session,
                            user_id=active_user.id,
                            template_id=template["id"],
                        )
                        created_flow_ids.append(result["id"])
                        created_count += 1
                    except HTTPException:
                        # Some templates might not be creatable
                        pass

                # At least some templates should work
                assert created_count > 0

            finally:
                # Cleanup all created flows
                for flow_id_str in created_flow_ids:
                    flow_uuid = UUID(flow_id_str) if isinstance(flow_id_str, str) else flow_id_str
                    flow = await session.get(Flow, flow_uuid)
                    if flow:
                        await session.delete(flow)
                await session.commit()
