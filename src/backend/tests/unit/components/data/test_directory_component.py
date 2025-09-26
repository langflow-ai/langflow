import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from lfx.components.data import DirectoryComponent
from lfx.schema import Data, DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestDirectoryComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return DirectoryComponent

    @pytest.fixture
    def default_kwargs(self, tmp_path):
        """Return the default kwargs for the component."""
        return {
            "path": str(tmp_path),
            "recursive": True,
            "use_multithreading": False,
            "silent_errors": False,
            "types": ["txt"],
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return [
            {"version": "1.0.19", "module": "data", "file_name": "Directory"},
            {"version": "1.1.0", "module": "data", "file_name": "directory"},
            {"version": "1.1.1", "module": "data", "file_name": "directory"},
        ]

    @patch("lfx.components.data.directory.parallel_load_data")
    @patch("lfx.components.data.directory.retrieve_file_paths")
    @patch("lfx.components.data.DirectoryComponent.resolve_path")
    def test_directory_component_build_with_multithreading(
        self, mock_resolve_path, mock_retrieve_file_paths, mock_parallel_load_data
    ):
        # Arrange
        directory_component = DirectoryComponent()
        path = Path(__file__).resolve().parent
        depth = 1
        max_concurrency = 2
        load_hidden = False
        recursive = True
        silent_errors = False
        use_multithreading = True

        mock_resolve_path.return_value = str(path)
        mock_retrieve_file_paths.return_value = [str(p) for p in path.iterdir() if p.suffix == ".py"]
        mock_parallel_load_data.return_value = [Mock()]

        # Act
        directory_component.set_attributes(
            {
                "path": str(path),
                "depth": depth,
                "max_concurrency": max_concurrency,
                "load_hidden": load_hidden,
                "recursive": recursive,
                "silent_errors": silent_errors,
                "use_multithreading": use_multithreading,
                "types": ["py"],  # Add file types without dots
            }
        )
        directory_component.load_directory()

        # Assert
        mock_resolve_path.assert_called_once_with(str(path))
        mock_retrieve_file_paths.assert_called_once_with(
            mock_resolve_path.return_value,
            depth=depth,
            recursive=recursive,
            types=["py"],
            load_hidden=load_hidden,
        )
        mock_parallel_load_data.assert_called_once_with(
            mock_retrieve_file_paths.return_value,
            max_concurrency=max_concurrency,
            silent_errors=silent_errors,
        )

    def test_directory_without_mocks(self):
        directory_component = DirectoryComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "test.txt").write_text("test", encoding="utf-8")
            # also add a json file
            (Path(temp_dir) / "test.json").write_text('{"test": "test"}', encoding="utf-8")

            directory_component.set_attributes(
                {
                    "path": str(temp_dir),
                    "use_multithreading": False,
                    "silent_errors": False,
                    "types": ["txt", "json"],
                }
            )
            results = directory_component.load_directory()
            assert len(results) == 2
            values = ["test", '{"test":"test"}']
            assert all(result.text in values for result in results), [
                (len(result.text), len(val)) for result, val in zip(results, values, strict=True)
            ]

        # in ../docs/docs/components there are many mdx files
        # check if the directory component can load them
        # just check if the number of results is the same as the number of files
        directory_component = DirectoryComponent()
        docs_path = Path(__file__).parent.parent.parent.parent.parent.parent.parent / "docs" / "docs" / "Components"
        directory_component.set_attributes(
            {
                "path": str(docs_path),
                "use_multithreading": False,
                "silent_errors": False,
                "types": ["md", "json"],
            }
        )
        results = directory_component.load_directory()
        docs_files = list(docs_path.glob("*.md")) + list(docs_path.glob("*.json"))
        assert len(results) == len(docs_files)

    def test_directory_as_dataframe(self):
        """Test DirectoryComponent's as_dataframe method."""
        directory_component = DirectoryComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files with different content
            files_content = {
                "file1.txt": "content1",
                "file2.json": '{"key": "content2"}',
                "file3.md": "# content3",
            }

            for filename, content in files_content.items():
                (Path(temp_dir) / filename).write_text(content, encoding="utf-8")

            directory_component.set_attributes(
                {
                    "path": str(temp_dir),
                    "use_multithreading": False,
                    "types": ["txt", "json", "md"],
                    "silent_errors": False,
                }
            )

            # Test as_dataframe
            data_frame = directory_component.as_dataframe()

            # Verify DataFrame structure
            assert isinstance(data_frame, DataFrame), "Expected DataFrame instance"
            assert len(data_frame) == 3, f"Expected DataFrame with 3 rows, got {len(data_frame)}"

            # Check column names
            expected_columns = ["text", "file_path"]
            actual_columns = list(data_frame.columns)
            assert set(expected_columns).issubset(set(actual_columns)), (
                f"Missing required columns. Expected at least {expected_columns}, got {actual_columns}"
            )

            # Verify content matches input files
            texts = data_frame["text"].tolist()
            # For JSON files, the content is parsed and re-serialized
            expected_content = {
                "file1.txt": "content1",
                "file2.json": '{"key":"content2"}',  # JSON is re-serialized without spaces
                "file3.md": "# content3",
            }
            missing_content = [content for content in expected_content.values() if content not in texts]
            assert not missing_content, f"Missing expected content in DataFrame: {missing_content}"

            # Verify file paths are correct
            file_paths = data_frame["file_path"].tolist()
            expected_paths = [str(Path(temp_dir) / filename) for filename in files_content]
            missing_paths = [path for path in expected_paths if not any(path in fp for fp in file_paths)]
            assert not missing_paths, f"Missing expected file paths in DataFrame: {missing_paths}"

    def test_directory_with_depth(self):
        """Test DirectoryComponent with different depth settings."""
        directory_component = DirectoryComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a nested directory structure
            base_dir = Path(temp_dir)
            (base_dir / "level1").mkdir()
            (base_dir / "level1" / "level2").mkdir()

            # Create files at different levels
            (base_dir / "root.txt").write_text("root", encoding="utf-8")
            (base_dir / "level1" / "level1.txt").write_text("level1", encoding="utf-8")
            (base_dir / "level1" / "level2" / "level2.txt").write_text("level2", encoding="utf-8")

            # Test non-recursive (only root)
            directory_component.set_attributes(
                {
                    "path": str(temp_dir),
                    "recursive": False,  # Set recursive to False to get only root files
                    "use_multithreading": False,
                    "silent_errors": False,
                    "types": ["txt"],
                }
            )
            results_root = directory_component.load_directory()
            assert len(results_root) == 1, (
                "With recursive=False, expected 1 file (root.txt), "
                f"got {len(results_root)} files: {[d.data['file_path'] for d in results_root]}"
            )
            assert results_root[0].text == "root", f"Expected root file content 'root', got '{results_root[0].text}'"

            # Test recursive with all files
            directory_component.set_attributes(
                {
                    "path": str(temp_dir),
                    "recursive": True,
                    "use_multithreading": False,
                    "silent_errors": False,
                    "types": ["txt"],
                }
            )
            results_all = directory_component.load_directory()
            assert len(results_all) == 3, (
                "With recursive=True, expected 3 files (all files), "
                f"got {len(results_all)} files: {[d.data['file_path'] for d in results_all]}"
            )
            texts = sorted([r.text for r in results_all])
            expected_texts = sorted(["root", "level1", "level2"])
            assert texts == expected_texts, f"Expected texts {expected_texts}, got {texts}"

    @pytest.mark.parametrize(
        ("file_types", "expected_count"),
        [
            (["txt"], 1),
            (["json"], 1),
            (["txt", "json"], 2),
        ],
    )
    def test_directory_with_types(self, file_types, expected_count):
        """Test DirectoryComponent with different file type filters (parameterized)."""
        directory_component = DirectoryComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with different extensions
            (Path(temp_dir) / "test.txt").write_text("text content", encoding="utf-8")
            (Path(temp_dir) / "test.json").write_text('{"key": "value"}', encoding="utf-8")
            (Path(temp_dir) / "test.exe").write_text("test", encoding="utf-8")

            directory_component.set_attributes(
                {
                    "path": str(temp_dir),
                    "types": file_types,
                    "use_multithreading": False,
                    "silent_errors": False,
                }
            )
            results = directory_component.load_directory()

            # Verify number of loaded files
            assert len(results) == expected_count, (
                f"Expected {expected_count} results for file types {file_types}, got {len(results)}"
            )
            # Optionally, check the file extension in each result
            for r in results:
                # e.g., verify that the extension is indeed in file_types
                file_ext = Path(r.data["file_path"]).suffix.lstrip(".")
                assert file_ext in file_types, f"Unexpected file extension: {file_ext}"

    def test_directory_invalid_type(self):
        """Test DirectoryComponent raises error with invalid file type."""
        directory_component = DirectoryComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            (Path(temp_dir) / "test.exe").write_text("test", encoding="utf-8")

            directory_component.set_attributes(
                {
                    "path": str(temp_dir),
                    "types": ["exe"],
                    "use_multithreading": False,
                    "silent_errors": False,
                }
            )

            with pytest.raises(
                ValueError, match=r"Invalid file types specified: \['exe'\]\. Valid types are:"
            ) as exc_info:
                directory_component.load_directory()

            assert "Invalid file types specified: ['exe']" in str(exc_info.value)
            assert "Valid types are:" in str(exc_info.value)

    def test_directory_with_hidden_files(self):
        """Test DirectoryComponent with hidden files."""
        directory_component = DirectoryComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create regular and hidden files
            (Path(temp_dir) / "regular.txt").write_text("regular", encoding="utf-8")
            (Path(temp_dir) / ".hidden.txt").write_text("hidden", encoding="utf-8")

            # Test without loading hidden files
            directory_component.set_attributes(
                {
                    "path": str(temp_dir),
                    "load_hidden": False,
                    "use_multithreading": False,
                    "silent_errors": False,
                    "types": ["txt"],
                }
            )
            results = directory_component.load_directory()
            assert len(results) == 1
            assert results[0].text == "regular"

            # Test with loading hidden files
            directory_component.set_attributes({"load_hidden": True})
            results = directory_component.load_directory()
            assert len(results) == 2
            texts = [r.text for r in results]
            assert "regular" in texts
            assert "hidden" in texts

    @patch("lfx.components.data.directory.parallel_load_data")
    def test_directory_with_multithreading(self, mock_parallel_load):
        """Test DirectoryComponent with multithreading enabled."""
        directory_component = DirectoryComponent()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            (Path(temp_dir) / "test1.txt").write_text("content1", encoding="utf-8")
            (Path(temp_dir) / "test2.txt").write_text("content2", encoding="utf-8")

            # Mock parallel_load_data to return some test data
            mock_data = [
                Data(text="content1", data={"file_path": str(Path(temp_dir) / "test1.txt")}),
                Data(text="content2", data={"file_path": str(Path(temp_dir) / "test2.txt")}),
            ]
            mock_parallel_load.return_value = mock_data

            # Test with multithreading enabled
            directory_component.set_attributes(
                {
                    "path": str(temp_dir),
                    "use_multithreading": True,
                    "max_concurrency": 2,
                    "types": ["txt"],  # Specify file types to ensure files are found
                    "recursive": True,  # Enable recursive search
                    "silent_errors": False,
                }
            )
            results = directory_component.load_directory()

            # Verify parallel_load_data was called with correct parameters
            mock_parallel_load.assert_called_once()
            call_args = mock_parallel_load.call_args[1]
            assert call_args["max_concurrency"] == 2, (
                f"Expected max_concurrency=2, got {call_args.get('max_concurrency')}"
            )
            assert call_args["silent_errors"] is False, (
                f"Expected silent_errors=False, got {call_args.get('silent_errors')}"
            )

            # Verify results
            assert len(results) == 2, (
                f"Expected 2 results, got {len(results)}: {[r.data['file_path'] for r in results]}"
            )
            assert all(isinstance(r, Data) for r in results), (
                f"All results should be Data objects, got types: {[type(r) for r in results]}"
            )

            actual_texts = [r.text for r in results]
            expected_texts = ["content1", "content2"]
            assert actual_texts == expected_texts, f"Expected texts {expected_texts}, got {actual_texts}"
