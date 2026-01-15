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
    _is_sensitive_key,
    sanitize_data,
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
        """Test that 'code' key is filtered from inputs via sanitize_data."""
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

    def test_transaction_base_sanitizes_sensitive_data_in_inputs(self):
        """Test that sensitive data like api_key is masked in inputs."""
        flow_id = uuid4()
        inputs_with_api_key = {
            "api_key": "sk-proj-MBZ6RyzaqpMgw_wwa123456789",
            "template": "Hello world",
        }
        transaction = TransactionBase(
            vertex_id="test-vertex",
            inputs=inputs_with_api_key,
            status="success",
            flow_id=flow_id,
        )

        # The api_key should be masked
        assert transaction.inputs["api_key"] == "sk-p...6789"
        # Non-sensitive data should remain unchanged
        assert transaction.inputs["template"] == "Hello world"

    def test_transaction_base_sanitizes_sensitive_data_in_outputs(self):
        """Test that sensitive data like password is masked in outputs."""
        flow_id = uuid4()
        # Short password (<=12 chars) should be fully redacted
        outputs_with_short_password = {
            "password": "short",
            "result": "success",
        }
        transaction = TransactionBase(
            vertex_id="test-vertex",
            outputs=outputs_with_short_password,
            status="success",
            flow_id=flow_id,
        )

        # Short passwords should be fully redacted
        assert transaction.outputs["password"] == "***REDACTED***"  # noqa: S105
        # Non-sensitive data should remain unchanged
        assert transaction.outputs["result"] == "success"

        # Long password (>12 chars) should be partially masked
        outputs_with_long_password = {
            "password": "supersecret123456",
            "result": "ok",
        }
        transaction2 = TransactionBase(
            vertex_id="test-vertex-2",
            outputs=outputs_with_long_password,
            status="success",
            flow_id=flow_id,
        )

        # Long passwords should show first 4 and last 4 chars
        assert transaction2.outputs["password"] == "supe...3456"  # noqa: S105
        assert transaction2.outputs["result"] == "ok"

    def test_transaction_base_sanitizes_nested_sensitive_data(self):
        """Test that nested sensitive data is also masked."""
        flow_id = uuid4()
        inputs_nested = {
            "config": {
                "openai_api_key": "sk-12345678901234567890",
                "model": "gpt-4",
            },
            "text": "Hello",
        }
        transaction = TransactionBase(
            vertex_id="test-vertex",
            inputs=inputs_nested,
            status="success",
            flow_id=flow_id,
        )

        # Nested api_key should be masked
        assert transaction.inputs["config"]["openai_api_key"] == "sk-1...7890"
        # Non-sensitive nested data should remain unchanged
        assert transaction.inputs["config"]["model"] == "gpt-4"
        assert transaction.inputs["text"] == "Hello"

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


class TestSanitizeData:
    """Tests for the sanitize_data function and related utilities."""

    def test_sanitize_data_returns_none_for_none_input(self):
        """Test that sanitize_data returns None when input is None."""
        assert sanitize_data(None) is None

    def test_sanitize_data_masks_api_key(self):
        """Test that api_key values are masked."""
        data = {"api_key": "sk-proj-1234567890abcdef"}
        result = sanitize_data(data)
        assert result["api_key"] == "sk-p...cdef"

    def test_sanitize_data_masks_password(self):
        """Test that password values are masked."""
        data = {"password": "short"}
        result = sanitize_data(data)
        assert result["password"] == "***REDACTED***"  # noqa: S105

    def test_sanitize_data_masks_various_sensitive_keys(self):
        """Test that various sensitive key patterns are masked."""
        data = {
            "api_key": "sk-1234567890123456",
            "api-key": "sk-1234567890123456",
            "apikey": "sk-1234567890123456",
            "password": "secretpassword123",
            "secret": "mysecret12345678",
            "token": "mytoken123456789",
            "credential": "mycredential1234",
            "auth": "myauthvalue12345",
            "bearer": "mybearertoken123",
            "private_key": "myprivatekey1234",
            "access_key": "myaccesskey12345",
        }
        result = sanitize_data(data)

        for key in data:
            # All sensitive keys should be masked
            assert "***" in result[key] or "..." in result[key], f"Key '{key}' was not masked"

    def test_sanitize_data_preserves_non_sensitive_data(self):
        """Test that non-sensitive data is preserved."""
        data = {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = sanitize_data(data)
        assert result == data

    def test_sanitize_data_handles_nested_dicts(self):
        """Test that nested dictionaries are sanitized."""
        data = {
            "config": {
                "api_key": "sk-nested12345678901",
                "model": "gpt-4",
            }
        }
        result = sanitize_data(data)
        assert "..." in result["config"]["api_key"]
        assert result["config"]["model"] == "gpt-4"

    def test_sanitize_data_handles_lists(self):
        """Test that lists containing dicts are sanitized."""
        data = {
            "items": [
                {"api_key": "sk-list1234567890123", "name": "item1"},
                {"api_key": "sk-list1234567890124", "name": "item2"},
            ]
        }
        result = sanitize_data(data)
        assert "..." in result["items"][0]["api_key"]
        assert "..." in result["items"][1]["api_key"]
        assert result["items"][0]["name"] == "item1"
        assert result["items"][1]["name"] == "item2"

    def test_sanitize_data_removes_code_key(self):
        """Test that 'code' key is completely removed."""
        data = {"code": "def foo(): pass", "value": "keep me"}
        result = sanitize_data(data)
        assert "code" not in result
        assert result["value"] == "keep me"

    def test_sanitize_data_case_insensitive(self):
        """Test that key matching is case insensitive."""
        data = {
            "API_KEY": "sk-upper1234567890123",
            "Password": "mixedcase123456",
            "SECRET": "allcaps12345678901",
        }
        result = sanitize_data(data)
        for key in data:
            assert "***" in result[key] or "..." in result[key], f"Key '{key}' was not masked"

    def test_is_sensitive_key_matches_expected_keys(self):
        """Test that _is_sensitive_key correctly identifies sensitive keys."""
        should_match = [
            "api_key",
            "api-key",
            "apikey",
            "API_KEY",
            "password",
            "PASSWORD",
            "secret",
            "SECRET",
            "token",
            "TOKEN",
            "credential",
            "CREDENTIAL",
            "auth",
            "AUTH",
            "bearer",
            "BEARER",
            "private_key",
            "private-key",
            "access_key",
            "access-key",
            "openai_api_key",
            "anthropic_api_key",
            "auth_token",
            "access_token",
        ]
        for key in should_match:
            assert _is_sensitive_key(key), f"Key '{key}' should be identified as sensitive"

        should_not_match = [
            "model",
            "temperature",
            "max_tokens",
            "messages",
            "name",
            "value",
            "result",
            "status",
            "author",
            "authentication_method",
        ]
        for key in should_not_match:
            assert not _is_sensitive_key(key), f"Key '{key}' should NOT be identified as sensitive"


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
            TransactionTable(id=uuid4(), vertex_id=f"vertex-{i}", status="success", flow_id=uuid4()) for i in range(3)
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
            TransactionTable(id=uuid4(), vertex_id=f"vertex-{i}", status="success", flow_id=uuid4()) for i in range(3)
        ]

        result = transform_transaction_table_for_logs(tables)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(r, TransactionLogsResponse) for r in result)


class TestTransactionWithOutputs:
    """Tests for transaction with explicit outputs parameter."""

    def test_transaction_base_with_explicit_outputs(self):
        """Test creating TransactionBase with explicit outputs dict."""
        flow_id = uuid4()
        outputs = {
            "output": {"message": "Hello World", "type": "text"},
            "another_output": {"message": {"key": "value"}, "type": "object"},
        }
        transaction = TransactionBase(
            vertex_id="test-vertex",
            inputs={"input_value": "test"},
            outputs=outputs,
            status="success",
            flow_id=flow_id,
        )

        assert transaction.outputs is not None
        assert "output" in transaction.outputs
        assert transaction.outputs["output"]["message"] == "Hello World"
        assert transaction.outputs["output"]["type"] == "text"

    def test_transaction_base_outputs_sanitization(self):
        """Test that outputs with sensitive data are sanitized."""
        flow_id = uuid4()
        outputs = {
            "result": {
                "message": "success",
                "api_key": "sk-1234567890abcdef1234",
            }
        }
        transaction = TransactionBase(
            vertex_id="test-vertex",
            outputs=outputs,
            status="success",
            flow_id=flow_id,
        )

        # The nested api_key should be masked
        assert "..." in transaction.outputs["result"]["api_key"]
        assert transaction.outputs["result"]["message"] == "success"

    def test_transaction_table_with_outputs(self):
        """Test creating TransactionTable with outputs."""
        flow_id = uuid4()
        outputs = {"component_output": {"message": "Built successfully", "type": "text"}}
        table = TransactionTable(
            id=uuid4(),
            vertex_id="test-vertex",
            inputs={"param": "value"},
            outputs=outputs,
            status="success",
            flow_id=flow_id,
        )

        assert table.outputs is not None
        assert "component_output" in table.outputs
        assert table.outputs["component_output"]["message"] == "Built successfully"

    def test_transaction_logs_response_includes_outputs(self):
        """Test that TransactionLogsResponse includes outputs field."""
        table = TransactionTable(
            id=uuid4(),
            vertex_id="test-vertex",
            inputs={"input": "data"},
            outputs={"output": {"message": "result", "type": "text"}},
            status="success",
            flow_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        )

        response = TransactionLogsResponse.model_validate(table, from_attributes=True)

        assert response.outputs is not None
        assert "output" in response.outputs


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
