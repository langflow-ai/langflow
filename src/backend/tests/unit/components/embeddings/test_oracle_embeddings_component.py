from unittest.mock import MagicMock, patch

import pytest
from langchain_oracledb import OracleEmbeddings
from lfx.components.oracledb.oracledb_embeddings import OracleEmbeddingsComponent

from tests.oracle_test_utils import (
    get_oracle_connection_inputs,
    get_oracle_connection_params,
    get_oracle_embedding_params,
    get_oracle_test_connection_inputs,
)


def test_oracle_embeddings_connection_secrets_are_password_inputs():
    inputs = {input_.name: input_ for input_ in OracleEmbeddingsComponent.inputs}

    for name in ("user", "password", "dsn", "wallet_password", "proxy"):
        assert inputs[name].password is True

    assert inputs["connection_params"].advanced is True
    assert "Non-secret" in inputs["connection_params"].info


def test_build_embeddings_returns_oracle_embeddings_instance():
    connection_params = get_oracle_connection_params()
    if connection_params:
        component = OracleEmbeddingsComponent().set(
            **get_oracle_connection_inputs(connection_params),
            embedding_params=get_oracle_embedding_params(),
        )

        result = component.build_embeddings()

        assert isinstance(result, OracleEmbeddings)
        return

    with (
        patch("lfx.components.oracledb.oracledb_embeddings.OracleEmbeddings") as mock_oracle_embeddings,
        patch("lfx.components.oracledb.oracledb_embeddings.oracledb.connect") as mock_connect,
    ):
        connection = MagicMock()
        embeddings = MagicMock()
        mock_connect.return_value = connection
        mock_oracle_embeddings.return_value = embeddings
        test_connection_inputs = get_oracle_test_connection_inputs()

        component = OracleEmbeddingsComponent().set(
            dsn=test_connection_inputs["dsn"],
            embedding_params={"provider": "database", "model": "ALL_MINILM_L12_V2"},
            proxy="http://proxy.internal",
        )

        result = component.build_embeddings()

    assert result is embeddings
    mock_connect.assert_called_once_with(dsn=test_connection_inputs["dsn"])
    mock_oracle_embeddings.assert_called_once_with(
        conn=connection,
        params={"provider": "database", "model": "ALL_MINILM_L12_V2"},
        proxy="http://proxy.internal",
    )


def test_build_embeddings_accepts_credentialized_dsn_without_user_password():
    connection_params = get_oracle_connection_params()
    if connection_params:
        user = connection_params.get("user") or connection_params.get("username")
        password = connection_params.get("password")
        dsn = connection_params.get("dsn") or connection_params.get("connection_string") or connection_params.get("tns")

        if user and password and dsn:
            credentialized_dsn = f"{user}/{password}@{dsn}"
        elif isinstance(dsn, str) and "/" in dsn and "@" in dsn:
            credentialized_dsn = dsn
        else:
            pytest.skip("Credentialized DSN test requires split credentials or an already credentialized DSN.")

        component = OracleEmbeddingsComponent().set(
            dsn=credentialized_dsn,
            embedding_params=get_oracle_embedding_params(),
        )

        result = component.build_embeddings()

        assert isinstance(result, OracleEmbeddings)
        return

    with (
        patch("lfx.components.oracledb.oracledb_embeddings.OracleEmbeddings") as mock_oracle_embeddings,
        patch("lfx.components.oracledb.oracledb_embeddings.oracledb.connect") as mock_connect,
    ):
        connection = MagicMock()
        embeddings = MagicMock()
        mock_connect.return_value = connection
        mock_oracle_embeddings.return_value = embeddings
        test_connection_inputs = get_oracle_test_connection_inputs()

        component = OracleEmbeddingsComponent().set(
            dsn=f"{test_connection_inputs['user']}/{test_connection_inputs['password']}@{test_connection_inputs['dsn']}",
            embedding_params={"provider": "database", "model": "ALL_MINILM_L12_V2"},
        )

        result = component.build_embeddings()

    assert result is embeddings
    mock_connect.assert_called_once_with(**test_connection_inputs)


@patch("lfx.components.oracledb.oracledb_embeddings.OracleEmbeddings")
@patch("lfx.components.oracledb.oracledb_embeddings.oracledb.connect")
def test_build_embeddings_passes_none_proxy_when_unset(mock_connect, mock_oracle_embeddings):
    connection = MagicMock()
    embeddings = MagicMock()
    mock_connect.return_value = connection
    mock_oracle_embeddings.return_value = embeddings
    test_connection_inputs = get_oracle_test_connection_inputs()

    component = OracleEmbeddingsComponent().set(
        **test_connection_inputs,
        embedding_params={"provider": "database", "model": "ALL_MINILM_L12_V2"},
    )

    result = component.build_embeddings()

    assert result is embeddings
    mock_connect.assert_called_once_with(**test_connection_inputs)
    mock_oracle_embeddings.assert_called_once_with(
        conn=connection,
        params={"provider": "database", "model": "ALL_MINILM_L12_V2"},
        proxy=None,
    )


@patch("lfx.components.oracledb.oracledb_embeddings.OracleEmbeddings")
@patch("lfx.components.oracledb.oracledb_embeddings.oracledb.connect")
def test_build_embeddings_wraps_oracle_embeddings_errors(mock_connect, mock_oracle_embeddings):
    connection = MagicMock()
    mock_connect.return_value = connection
    mock_oracle_embeddings.side_effect = RuntimeError("boom")
    test_connection_inputs = get_oracle_test_connection_inputs()

    component = OracleEmbeddingsComponent().set(
        dsn=test_connection_inputs["dsn"],
        embedding_params={"provider": "database", "model": "ALL_MINILM_L12_V2"},
    )

    with pytest.raises(ValueError, match="Unable to create OracleEmbeddings\\.") as exc_info:
        component.build_embeddings()

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert str(exc_info.value.__cause__) == "boom"
    connection.close.assert_called_once_with()


@patch("lfx.components.oracledb.oracledb_embeddings.oracledb.connect")
def test_build_embeddings_propagates_connection_errors(mock_connect):
    mock_connect.side_effect = RuntimeError("connect boom")
    test_connection_inputs = get_oracle_test_connection_inputs()

    component = OracleEmbeddingsComponent().set(
        dsn=test_connection_inputs["dsn"],
        embedding_params={"provider": "database", "model": "ALL_MINILM_L12_V2"},
    )

    with pytest.raises(RuntimeError, match="connect boom"):
        component.build_embeddings()
