from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from lfx.utils.file_path_security import LocalFileAccessError
from lfx_oracle.components.oracle.oracledb_loaders import (
    OracleAutonomousDatabaseLoaderComponent,
    OracleDocLoaderComponent,
)
from oracle_test_utils import get_oracle_test_connection_inputs

_DOC_LOADER_OPTIONS = ("file", "dir", "config_dir", "wallet_location")
_CONNECTION_OPTIONS = ("config_dir", "wallet_location")


def _settings(*, restricted: bool, config_dir: str) -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(
            restrict_local_file_access=restricted,
            config_dir=config_dir,
            database_url="",
        )
    )


def _doc_component(*, path_option: str, path: str) -> OracleDocLoaderComponent:
    params = {"owner": "owner", "tablename": "documents", "colname": "content"}
    connection_params = {}
    if path_option in {"file", "dir"}:
        params[path_option] = path
    else:
        connection_params[path_option] = path
    component = OracleDocLoaderComponent().set(
        dsn="db.invalid/service",
        params=params,
        connection_params=connection_params,
    )
    component._user_id = "owner"
    return component


def _autonomous_component(*, path_option: str, path: str) -> OracleAutonomousDatabaseLoaderComponent:
    component = OracleAutonomousDatabaseLoaderComponent().set(
        query="SELECT 1 FROM dual",
        **get_oracle_test_connection_inputs(),
        connection_params={path_option: path},
    )
    component._user_id = "owner"
    return component


@pytest.mark.parametrize("path_option", _DOC_LOADER_OPTIONS)
def test_oracle_doc_loader_denies_outside_paths_when_restricted(tmp_path, path_option: str) -> None:
    storage = tmp_path / "storage"
    outside = tmp_path / "outside" / path_option
    component = _doc_component(path_option=path_option, path=str(outside))
    expected_error = (
        "Directory loading is not permitted"
        if path_option == "dir"
        else "outside the authenticated user's storage scope"
    )

    with (
        patch(
            "lfx.utils.file_path_security.get_settings_service",
            return_value=_settings(restricted=True, config_dir=str(storage)),
        ),
        patch("lfx_oracle.components.oracle.oracledb_loaders.oracledb.connect") as mock_connect,
        patch("lfx_oracle.components.oracle.oracledb_loaders.OracleDocLoader") as mock_loader,
        pytest.raises(LocalFileAccessError, match=expected_error),
    ):
        component.load_documents()

    mock_connect.assert_not_called()
    mock_loader.assert_not_called()


@pytest.mark.parametrize("path_option", _DOC_LOADER_OPTIONS)
def test_oracle_doc_loader_allows_outside_paths_when_unrestricted(tmp_path, path_option: str) -> None:
    storage = tmp_path / "storage"
    outside = tmp_path / "outside" / path_option
    component = _doc_component(path_option=path_option, path=str(outside))

    with (
        patch(
            "lfx.utils.file_path_security.get_settings_service",
            return_value=_settings(restricted=False, config_dir=str(storage)),
        ),
        patch("lfx_oracle.components.oracle.oracledb_loaders.oracledb.connect") as mock_connect,
        patch("lfx_oracle.components.oracle.oracledb_loaders.OracleDocLoader") as mock_loader,
    ):
        mock_loader.return_value.load.return_value = []
        assert component.load_documents() == []

    mock_connect.assert_called_once()
    mock_loader.assert_called_once()
    if path_option in {"file", "dir"}:
        assert mock_loader.call_args.args[1][path_option] == str(outside)
    else:
        assert mock_connect.call_args.kwargs[path_option] == str(outside)


def test_oracle_doc_loader_allows_file_and_connection_paths_inside_component_scope(tmp_path) -> None:
    storage = tmp_path / "storage"
    allowed = storage / "owner" / "input"
    params = {"file": str(allowed / "document.pdf")}
    connection_params = {
        "config_dir": str(allowed / "config"),
        "wallet_location": str(allowed / "wallet"),
    }
    component = OracleDocLoaderComponent().set(
        dsn="db.invalid/service",
        params=params,
        connection_params=connection_params,
    )
    component._user_id = "owner"

    with (
        patch(
            "lfx.utils.file_path_security.get_settings_service",
            return_value=_settings(restricted=True, config_dir=str(storage)),
        ),
        patch("lfx_oracle.components.oracle.oracledb_loaders.oracledb.connect") as mock_connect,
        patch("lfx_oracle.components.oracle.oracledb_loaders.OracleDocLoader") as mock_loader,
    ):
        mock_loader.return_value.load.return_value = []
        assert component.load_documents() == []

    assert mock_connect.call_args.kwargs["config_dir"] == connection_params["config_dir"]
    assert mock_connect.call_args.kwargs["wallet_location"] == connection_params["wallet_location"]
    assert mock_loader.call_args.args[1] == params


def test_oracle_doc_loader_rejects_directory_mode_when_restricted(tmp_path) -> None:
    storage = tmp_path / "storage"
    directory = storage / "owner" / "documents"
    directory.mkdir(parents=True)
    (directory / "document.pdf").touch()
    component = _doc_component(path_option="dir", path=str(directory))

    with (
        patch(
            "lfx.utils.file_path_security.get_settings_service",
            return_value=_settings(restricted=True, config_dir=str(storage)),
        ),
        patch("lfx_oracle.components.oracle.oracledb_loaders.oracledb.connect") as mock_connect,
        patch("lfx_oracle.components.oracle.oracledb_loaders.OracleDocLoader") as mock_loader,
        pytest.raises(LocalFileAccessError, match="Directory loading is not permitted"),
    ):
        component.load_documents()

    mock_connect.assert_not_called()
    mock_loader.assert_not_called()


def test_oracle_doc_loader_rejects_directory_symlinks_fail_closed_when_restricted(tmp_path) -> None:
    storage = tmp_path / "storage"
    directory = storage / "owner" / "documents"
    directory.mkdir(parents=True)
    outside = tmp_path / "outside.pdf"
    outside.touch()
    (directory / "linked.pdf").symlink_to(outside)
    component = _doc_component(path_option="dir", path=str(directory))

    with (
        patch(
            "lfx.utils.file_path_security.get_settings_service",
            return_value=_settings(restricted=True, config_dir=str(storage)),
        ),
        patch("lfx_oracle.components.oracle.oracledb_loaders.oracledb.connect") as mock_connect,
        patch("lfx_oracle.components.oracle.oracledb_loaders.OracleDocLoader") as mock_loader,
        pytest.raises(LocalFileAccessError, match="Directory loading is not permitted"),
    ):
        component.load_documents()

    mock_connect.assert_not_called()
    mock_loader.assert_not_called()


@pytest.mark.parametrize("path_option", _CONNECTION_OPTIONS)
def test_oracle_autonomous_loader_denies_outside_paths_when_restricted(tmp_path, path_option: str) -> None:
    storage = tmp_path / "storage"
    outside = tmp_path / "outside" / path_option
    component = _autonomous_component(path_option=path_option, path=str(outside))

    with (
        patch(
            "lfx.utils.file_path_security.get_settings_service",
            return_value=_settings(restricted=True, config_dir=str(storage)),
        ),
        patch("lfx_oracle.components.oracle.oracledb_loaders.OracleAutonomousDatabaseLoader") as mock_loader,
        pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"),
    ):
        component.load_documents()

    mock_loader.assert_not_called()


@pytest.mark.parametrize("path_option", _CONNECTION_OPTIONS)
def test_oracle_autonomous_loader_allows_outside_paths_when_unrestricted(tmp_path, path_option: str) -> None:
    storage = tmp_path / "storage"
    outside = tmp_path / "outside" / path_option
    component = _autonomous_component(path_option=path_option, path=str(outside))

    with (
        patch(
            "lfx.utils.file_path_security.get_settings_service",
            return_value=_settings(restricted=False, config_dir=str(storage)),
        ),
        patch("lfx_oracle.components.oracle.oracledb_loaders.OracleAutonomousDatabaseLoader") as mock_loader,
    ):
        mock_loader.return_value.load.return_value = []
        assert component.load_documents() == []

    mock_loader.assert_called_once()
    assert mock_loader.call_args.kwargs[path_option] == str(outside)


def test_oracle_autonomous_loader_allows_connection_paths_inside_component_scope(tmp_path) -> None:
    storage = tmp_path / "storage"
    allowed = storage / "owner" / "input"
    connection_params = {
        "config_dir": str(allowed / "config"),
        "wallet_location": str(allowed / "wallet"),
    }
    component = OracleAutonomousDatabaseLoaderComponent().set(
        query="SELECT 1 FROM dual",
        **get_oracle_test_connection_inputs(),
        connection_params=connection_params,
    )
    component._user_id = "owner"

    with (
        patch(
            "lfx.utils.file_path_security.get_settings_service",
            return_value=_settings(restricted=True, config_dir=str(storage)),
        ),
        patch("lfx_oracle.components.oracle.oracledb_loaders.OracleAutonomousDatabaseLoader") as mock_loader,
    ):
        mock_loader.return_value.load.return_value = []
        assert component.load_documents() == []

    assert mock_loader.call_args.kwargs["config_dir"] == connection_params["config_dir"]
    assert mock_loader.call_args.kwargs["wallet_location"] == connection_params["wallet_location"]
