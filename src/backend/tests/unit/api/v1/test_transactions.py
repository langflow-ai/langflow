"""Tests for transactions API endpoints and models."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.transactions.crud import (
    transform_transaction_table,
    transform_transaction_table_for_logs,
)
from langflow.services.database.models.transactions.model import (
    TransactionBase,
    TransactionLogsResponse,
    TransactionReadResponse,
    TransactionTable,
)


class TestTransactionModels:
    """Tests for transaction model classes."""

    def test_transaction_base_creation(self):
        """Test creating a TransactionBase instance."""
        flow_id = uuid4()
        transaction = TransactionBase(
            vertex_id="test-vertex-123",
            target_id="target-vertex-456",
            inputs={"key": "value"},
            outputs={"result": "success"},
            status="success",
            flow_id=flow_id,
        )

        assert transaction.vertex_id == "test-vertex-123"
        assert transaction.target_id == "target-vertex-456"
        assert transaction.inputs == {"key": "value"}
        assert transaction.outputs == {"result": "success"}
        assert transaction.status == "success"
        assert transaction.flow_id == flow_id
        assert transaction.error is None

    def test_transaction_base_with_error(self):
        """Test creating a TransactionBase with error status."""
        flow_id = uuid4()
        transaction = TransactionBase(
            vertex_id="test-vertex-123",
            status="error",
            error="Something went wrong",
            flow_id=flow_id,
        )

        assert transaction.status == "error"
        assert transaction.error == "Something went wrong"

    def test_transaction_base_filters_code_from_inputs(self):
        """Test that 'code' key is filtered from inputs."""
        flow_id = uuid4()
        inputs_with_code = {"key": "value", "code": "def foo(): pass"}
        transaction = TransactionBase(
            vertex_id="test-vertex",
            inputs=inputs_with_code,
            status="success",
            flow_id=flow_id,
        )

        # The original dict should not be modified
        assert "code" in inputs_with_code
        # But the transaction inputs should not have 'code'
        assert "code" not in transaction.inputs
        assert transaction.inputs["key"] == "value"

    def test_transaction_base_flow_id_string_conversion(self):
        """Test that string flow_id is converted to UUID."""
        flow_id_str = "12345678-1234-5678-1234-567812345678"
        transaction = TransactionBase(
            vertex_id="test-vertex",
            status="success",
            flow_id=flow_id_str,
        )

        from uuid import UUID

        assert isinstance(transaction.flow_id, UUID)
        assert str(transaction.flow_id) == flow_id_str

    def test_transaction_logs_response_from_table(self):
        """Test creating TransactionLogsResponse from TransactionTable."""
        table = TransactionTable(
            id=uuid4(),
            vertex_id="test-vertex",
            target_id="target-vertex",
            inputs={"input": "data"},
            outputs={"output": "result"},
            status="success",
            error=None,
            flow_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        )

        response = TransactionLogsResponse.model_validate(table, from_attributes=True)

        assert response.id == table.id
        assert response.vertex_id == table.vertex_id
        assert response.target_id == table.target_id
        assert response.status == table.status
        # TransactionLogsResponse should not have error and flow_id fields
        assert not hasattr(response, "error") or "error" not in response.model_fields
        assert not hasattr(response, "flow_id") or "flow_id" not in response.model_fields


class TestTransactionTransformers:
    """Tests for transaction transformer functions."""

    def test_transform_transaction_table_single(self):
        """Test transforming a single TransactionTable."""
        table = TransactionTable(
            id=uuid4(),
            vertex_id="test-vertex",
            status="success",
            flow_id=uuid4(),
        )

        result = transform_transaction_table(table)
        assert isinstance(result, TransactionReadResponse)

    def test_transform_transaction_table_list(self):
        """Test transforming a list of TransactionTable."""
        tables = [
            TransactionTable(id=uuid4(), vertex_id=f"vertex-{i}", status="success", flow_id=uuid4())
            for i in range(3)
        ]

        result = transform_transaction_table(tables)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(r, TransactionReadResponse) for r in result)

    def test_transform_transaction_table_for_logs_single(self):
        """Test transforming a single TransactionTable for logs view."""
        table = TransactionTable(
            id=uuid4(),
            vertex_id="test-vertex",
            status="success",
            flow_id=uuid4(),
        )

        result = transform_transaction_table_for_logs(table)
        assert isinstance(result, TransactionLogsResponse)

    def test_transform_transaction_table_for_logs_list(self):
        """Test transforming a list of TransactionTable for logs view."""
        tables = [
            TransactionTable(id=uuid4(), vertex_id=f"vertex-{i}", status="success", flow_id=uuid4())
            for i in range(3)
        ]

        result = transform_transaction_table_for_logs(tables)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(r, TransactionLogsResponse) for r in result)


class TestTransactionsEndpoint:
    """Tests for the /monitor/transactions endpoint."""

    async def test_get_transactions_requires_auth(self, client: AsyncClient):
        """Test that GET /monitor/transactions requires authentication."""
        response = await client.get("api/v1/monitor/transactions?flow_id=00000000-0000-0000-0000-000000000000")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.usefixtures("active_user")
    async def test_get_transactions_returns_paginated_response(self, client: AsyncClient, logged_in_headers):
        """Test that GET /monitor/transactions returns paginated response."""
        flow_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"api/v1/monitor/transactions?flow_id={flow_id}", headers=logged_in_headers)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert "size" in result
        assert "pages" in result
        assert isinstance(result["items"], list)

    @pytest.mark.usefixtures("active_user")
    async def test_get_transactions_with_pagination_params(self, client: AsyncClient, logged_in_headers):
        """Test GET /monitor/transactions with custom pagination parameters."""
        flow_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"api/v1/monitor/transactions?flow_id={flow_id}&page=1&size=10", headers=logged_in_headers
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["page"] == 1
        assert result["size"] == 10

    @pytest.mark.usefixtures("active_user")
    async def test_get_transactions_requires_flow_id(self, client: AsyncClient, logged_in_headers):
        """Test that GET /monitor/transactions requires flow_id parameter."""
        response = await client.get("api/v1/monitor/transactions", headers=logged_in_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.usefixtures("active_user")
    async def test_get_transactions_invalid_flow_id_format(self, client: AsyncClient, logged_in_headers):
        """Test GET /monitor/transactions with invalid flow_id format."""
        response = await client.get("api/v1/monitor/transactions?flow_id=invalid-uuid", headers=logged_in_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.usefixtures("active_user")
    async def test_get_transactions_response_structure(self, client: AsyncClient, logged_in_headers):
        """Test that transaction response items have the expected structure."""
        flow_id = uuid4()
        response = await client.get(f"api/v1/monitor/transactions?flow_id={flow_id}", headers=logged_in_headers)

        assert response.status_code == status.HTTP_200_OK
        result = response.json()

        # Verify pagination structure
        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert "size" in result
        assert "pages" in result
        assert isinstance(result["items"], list)
