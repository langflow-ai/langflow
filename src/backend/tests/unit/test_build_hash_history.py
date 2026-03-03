import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the scripts directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "scripts"))

# Now we can import the script
from build_hash_history import _import_components, main, update_history


@pytest.fixture
def mock_modules_dict():
    """Create a mock modules_dict with a nested structure."""
    return {
        "category1": {
            "MyComponent": {
                "metadata": {
                    "component_id": "1234-5678-9012-3456",
                    "code_hash": "hash_v1",
                },
                "display_name": "MyComponent",
            },
            "AnotherComponent": {
                "metadata": {
                    "component_id": "2345-6789-0123-4567",
                    "code_hash": "hash_v2",
                },
                "display_name": "AnotherComponent",
            },
        },
        "category2": {
            "ThirdComponent": {
                "metadata": {
                    "component_id": "3456-7890-1234-5678",
                    "code_hash": "hash_v3",
                },
                "display_name": "ThirdComponent",
            },
        },
    }


def test_update_history_scenarios():
    """Test various scenarios for the update_history function."""
    history = {}
    component_name = "MyComponent"
    code_hash_v1 = "hash_v1"
    code_hash_v2 = "hash_v2"

    # Scenario 1: Initial version
    history = update_history(history, component_name, code_hash_v1, "0.3.0")
    assert history[component_name]["versions"]["0.3.0"] == code_hash_v1

    # Scenario 2: New patch version, same hash
    history = update_history(history, component_name, code_hash_v1, "0.3.1")
    assert history[component_name]["versions"]["0.3.1"] == code_hash_v1

    # Scenario 3: New patch version, new hash
    history = update_history(history, component_name, code_hash_v2, "0.3.2")
    assert history[component_name]["versions"]["0.3.2"] == code_hash_v2

    # Scenario 4: New minor version, same hash as an old version
    history = update_history(history, component_name, code_hash_v1, "0.4.0")
    assert history[component_name]["versions"]["0.4.0"] == code_hash_v1

    # Scenario 5: Update hash for the same version
    history = update_history(history, component_name, code_hash_v2, "0.5.0")
    assert history[component_name]["versions"]["0.5.0"] == code_hash_v2
    history = update_history(history, component_name, code_hash_v1, "0.5.0")
    assert history[component_name]["versions"]["0.5.0"] == code_hash_v1

    # Scenario 6: Overwriting a newer version with an older one should raise an error
    with pytest.raises(ValueError, match="already has a version"):
        update_history(history, component_name, code_hash_v1, "0.4.0")


def test_main_function(tmp_path, mock_modules_dict):
    """Test the main function with mock data."""
    history_file = tmp_path / "history.json"

    with (
        patch("build_hash_history._import_components") as mock_import,
        patch("build_hash_history.load_hash_history") as mock_load,
        patch("build_hash_history.save_hash_history") as mock_save,
        patch("build_hash_history.get_lfx_version") as mock_get_version,
        patch("build_hash_history.Path") as mock_path,
    ):
        mock_import.return_value = (mock_modules_dict, 3)
        mock_load.return_value = {}
        mock_get_version.return_value = "0.1.0"
        mock_path.return_value = history_file

        # Run main with mocked functions
        main([])

        mock_save.assert_called_once()
        saved_history = mock_save.call_args[0][1]

        assert len(saved_history) == 3
        assert "MyComponent" in saved_history
        assert saved_history["MyComponent"]["versions"]["0.1.0"] == "hash_v1"
        assert "AnotherComponent" in saved_history
        assert saved_history["AnotherComponent"]["versions"]["0.1.0"] == "hash_v2"
        assert "ThirdComponent" in saved_history
        assert saved_history["ThirdComponent"]["versions"]["0.1.0"] == "hash_v3"


def test_all_real_component_names_are_unique():
    """Test that all real component names loaded via _import_components are unique."""
    modules_dict, _ = _import_components()  # Load real components

    component_names = [
        component_name for components_dict in modules_dict.values() for component_name in components_dict
    ]

    assert len(component_names) == len(set(component_names))
