"""Tests for cloud-mode storage metadata on file components."""

from lfx.components.files_and_knowledge.file import FileComponent
from lfx.components.files_and_knowledge.save_file import SaveToFileComponent


def test_read_file_component_marks_local_storage_as_cloud_incompatible():
    assert FileComponent.metadata["cloud_incompatible_options"] == {
        "storage_location": ["Local"],
    }


def test_write_file_component_marks_local_storage_as_cloud_incompatible():
    assert SaveToFileComponent.metadata["cloud_incompatible_options"] == {
        "storage_location": ["Local"],
    }
