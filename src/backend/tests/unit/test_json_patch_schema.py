import pytest
from langflow.api.v1.schemas import JsonPatch, PatchOperation, PatchOperationType
from pydantic import ValidationError


@pytest.mark.unit
class TestJsonPatchSchema:
    """Test the JSON Patch schema validation."""

    def test_patch_operation_add(self):
        """Test add operation validation."""
        # Use model_validate to create the object
        data = {"op": "add", "path": "/name", "value": "New Name"}
        op = PatchOperation.model_validate(data)
        assert op.op == PatchOperationType.ADD
        assert op.path == "/name"
        assert op.value == "New Name"
        assert op.from_ is None

    def test_patch_operation_replace(self):
        """Test replace operation validation."""
        data = {"op": "replace", "path": "/description", "value": "New Description"}
        op = PatchOperation.model_validate(data)
        assert op.op == PatchOperationType.REPLACE
        assert op.path == "/description"
        assert op.value == "New Description"
        assert op.from_ is None

    def test_patch_operation_remove(self):
        """Test remove operation validation."""
        data = {"op": "remove", "path": "/tags/0"}
        op = PatchOperation.model_validate(data)
        assert op.op == PatchOperationType.REMOVE
        assert op.path == "/tags/0"
        assert op.value is None
        assert op.from_ is None

    def test_patch_operation_move(self):
        """Test move operation validation."""
        data = {"op": "move", "path": "/tags/1", "from": "/tags/0"}
        op = PatchOperation.model_validate(data)
        assert op.op == PatchOperationType.MOVE
        assert op.path == "/tags/1"
        assert op.from_ == "/tags/0"
        assert op.value is None

    def test_patch_operation_copy(self):
        """Test copy operation validation."""
        data = {"op": "copy", "path": "/tags/1", "from": "/tags/0"}
        op = PatchOperation.model_validate(data)
        assert op.op == PatchOperationType.COPY
        assert op.path == "/tags/1"
        assert op.from_ == "/tags/0"
        assert op.value is None

    def test_patch_operation_test(self):
        """Test test operation validation."""
        data = {"op": "test", "path": "/name", "value": "Test Name"}
        op = PatchOperation.model_validate(data)
        assert op.op == PatchOperationType.TEST
        assert op.path == "/name"
        assert op.value == "Test Name"
        assert op.from_ is None

    def test_patch_operation_invalid_path(self):
        """Test that an invalid path fails validation."""
        with pytest.raises(ValidationError):
            PatchOperation.model_validate(
                {
                    "op": "add",
                    "path": "name",  # Missing leading slash
                    "value": "New Name",
                }
            )

    def test_patch_operation_missing_from(self):
        """Test that missing from field fails validation for move/copy operations."""
        with pytest.raises(ValidationError):
            PatchOperation.model_validate(
                {
                    "op": "move",
                    "path": "/tags/1",
                    # Missing 'from' field
                }
            )

        with pytest.raises(ValidationError):
            PatchOperation.model_validate(
                {
                    "op": "copy",
                    "path": "/tags/1",
                    # Missing 'from' field
                }
            )

    def test_patch_operation_invalid_from(self):
        """Test that invalid from field fails validation for move/copy operations."""
        with pytest.raises(ValidationError):
            PatchOperation.model_validate(
                {
                    "op": "move",
                    "path": "/tags/1",
                    "from": "tags/0",  # Missing leading slash
                }
            )

        with pytest.raises(ValidationError):
            PatchOperation.model_validate(
                {
                    "op": "copy",
                    "path": "/tags/1",
                    "from": "tags/0",  # Missing leading slash
                }
            )

    def test_patch_operation_null_value_allowed_for_replace(self):
        """Test that null value is allowed for replace operations (used to clear fields)."""
        # Replace with null should be valid
        op = PatchOperation.model_validate(
            {
                "op": "replace",
                "path": "/endpoint_name",
                "value": None,
            }
        )
        assert op.op == PatchOperationType.REPLACE
        assert op.path == "/endpoint_name"
        assert op.value is None

    def test_json_patch_valid(self):
        """Test that a valid JSON Patch passes validation."""
        data = {
            "operations": [
                {"op": "add", "path": "/name", "value": "New Name"},
                {"op": "replace", "path": "/description", "value": "New Description"},
                {"op": "remove", "path": "/tags/0"},
            ]
        }
        patch = JsonPatch.model_validate(data)
        assert len(patch.operations) == 3
        assert patch.operations[0].op == PatchOperationType.ADD
        assert patch.operations[1].op == PatchOperationType.REPLACE
        assert patch.operations[2].op == PatchOperationType.REMOVE
