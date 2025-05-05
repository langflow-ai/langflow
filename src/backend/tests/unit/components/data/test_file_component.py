from unittest.mock import Mock

import pytest
from langflow.components.data import FileComponent

from tests.base import ComponentTestBaseWithoutClient


class TestFileComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return FileComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"use_multithreading": True, "concurrency_multithreading": 2, "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_process_files_with_no_files(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="No files to process."):
            component.process_files([])

    def test_process_files_sequentially(self, component_class, default_kwargs, tmp_path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content 1")
        file2.write_text("content 2")
        default_kwargs["use_multithreading"] = False

        component = component_class(**default_kwargs)
        mock_file_list = [Mock(path=str(file1)), Mock(path=str(file2))]
        result = component.process_files(mock_file_list)

        assert all(i.path in (str(file1), str(file2)) for i in result)

    def test_process_files_with_multithreading(self, component_class, default_kwargs, tmp_path):
        mock_file_list = []
        files = []
        for i in range(5):
            file = tmp_path / f"file{i}.txt"
            file.write_text(f"content {i}")
            files.append(file)
            mock_file_list.append(Mock(path=str(file)))

        component = component_class(**default_kwargs)
        result = component.process_files(mock_file_list)

        assert all(i.path in [f.path for f in mock_file_list] for i in result)

    def test_file_component_latest(self, component_class, default_kwargs, tmp_path):
        file = tmp_path / "latest_file.txt"
        file.write_text("latest content")

        component = component_class(**default_kwargs)
        mock_file_list = [Mock(path=str(file))]
        result = component.process_files(mock_file_list)

        assert len(result) == len(mock_file_list)
        assert all(i.path in [f.path for f in mock_file_list] for i in result)
