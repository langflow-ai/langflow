"""Saved Chroma component contracts remain loadable after SDK retirement."""

import inspect

import pytest
from lfx.base.knowledge_bases.backends.chroma import ChromaMigrationRequiredError
from lfx.components.chroma.local_db import LocalDBComponent
from lfx.custom.utils import eval_custom_component_code


def test_saved_component_identity_and_fields():
    component = LocalDBComponent()
    assert component.legacy is True
    assert {"collection_name", "persist_directory", "embedding", "search_type", "number_of_results"} <= {
        field.name for field in component.inputs
    }
    restored = eval_custom_component_code(inspect.getsource(inspect.getmodule(LocalDBComponent)))
    assert restored.__name__ == "LocalDBComponent"
    assert [field.name for field in restored.inputs] == [field.name for field in component.inputs]


def test_execution_requires_migration_and_does_not_touch_data(tmp_path):
    directory = tmp_path / "existing"
    directory.mkdir()
    original = directory / "chroma.sqlite3"
    original.write_bytes(b"retained-source")
    component = LocalDBComponent().set(collection_name="existing", persist_directory=str(directory))
    with pytest.raises(ChromaMigrationRequiredError, match="requires migration"):
        component.perform_search()
    assert original.read_bytes() == b"retained-source"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["existing"]
