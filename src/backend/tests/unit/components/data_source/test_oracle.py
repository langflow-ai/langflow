from __future__ import annotations

import re
from contextlib import suppress
from unittest.mock import MagicMock, patch

import oracledb
import pytest
from langchain_core.documents import Document
from lfx.components.oracledb.oracledb_loaders import (
    OracleAutonomousDatabaseLoaderComponent,
    OracleDocLoaderComponent,
)
from lfx.schema.data import Data

from tests.oracle_test_utils import (
    get_oracle_connection_inputs,
    get_oracle_connection_params,
    get_oracle_owner,
    get_oracle_test_connection_inputs,
)


@pytest.fixture(scope="module")
def connection_params() -> dict[str, str] | None:
    return get_oracle_connection_params()


@pytest.fixture
def dsn(connection_params: dict[str, str] | None) -> str | None:
    if not connection_params:
        return None
    return connection_params.get("dsn")


@pytest.fixture
def connection(connection_params: dict[str, str] | None):
    if not connection_params:
        yield None
        return

    conn = oracledb.connect(**connection_params)
    try:
        yield conn
    finally:
        with suppress(Exception):
            conn.close()


def _safe_identifier(name: str, max_len: int = 30) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", name).upper()
    # Ensure first char is a letter
    if not base or not base[0].isalpha():
        base = "T_" + base
    return base[:max_len]


def _drop_table_if_exists(cur: oracledb.Cursor, table_name: str) -> None:
    # Drop table if exists: ORA-00942 (table or view does not exist) -> ignore
    cur.execute(
        f"""
        BEGIN
            EXECUTE IMMEDIATE 'DROP TABLE {table_name} PURGE';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE != -942 THEN
                    RAISE;
                END IF;
        END;"""
    )


def _adb_expected_documents() -> list[Document]:
    return [
        Document(
            page_content="{'FIELD1': '1', 'FIELD_JSON': {'INNER_FIELD1': '1', 'INNER_FIELD2': '1'}}",
            metadata={"FIELD1": "1"},
        ),
        Document(
            page_content="{'FIELD1': '2', 'FIELD_JSON': {'INNER_FIELD1': '2', 'INNER_FIELD2': '2'}}",
            metadata={"FIELD1": "2"},
        ),
        Document(
            page_content="{'FIELD1': '3', 'FIELD_JSON': {'INNER_FIELD1': '3', 'INNER_FIELD2': '3'}}",
            metadata={"FIELD1": "3"},
        ),
    ]


def test_oracle_loader_connection_secrets_are_password_inputs() -> None:
    for component_class in (OracleDocLoaderComponent, OracleAutonomousDatabaseLoaderComponent):
        inputs = {input_.name: input_ for input_ in component_class.inputs}
        for name in ("user", "password", "dsn", "wallet_password"):
            assert inputs[name].password is True

        assert inputs["connection_params"].advanced is True
        assert "Non-secret" in inputs["connection_params"].info


def test_oracle_doc_loader_component_integration(
    request,
    connection: oracledb.Connection | None,
    connection_params: dict[str, str] | None,
) -> None:
    """Integration test for loading rows from OracleDocLoaderComponent."""
    if not connection_params:
        with (
            patch(
                "lfx.components.oracledb.oracledb_loaders.oracledb.connect",
                return_value=MagicMock(),
            ) as mock_connect,
            patch("lfx.components.oracledb.oracledb_loaders.OracleDocLoader") as mock_loader,
        ):
            mock_loader.return_value.load.return_value = [
                Document(page_content="row1"),
                Document(page_content="row2"),
            ]
            test_connection_inputs = get_oracle_test_connection_inputs()
            component = OracleDocLoaderComponent().set(
                dsn=test_connection_inputs["dsn"],
                params={"owner": "mock_owner", "tablename": "MOCK_TABLE", "colname": "MARKDOWN"},
            )

            data_list = component.load_documents()

        assert isinstance(data_list, list)
        assert len(data_list) == 2
        assert all(isinstance(d, Data) for d in data_list)
        assert {d.text for d in data_list} == {"row1", "row2"}
        assert component.status == data_list
        mock_connect.assert_called_once_with(dsn=test_connection_inputs["dsn"])
        mock_loader.assert_called_once()
        return

    assert connection is not None
    cur = connection.cursor()

    table_name = _safe_identifier(f"lfx_{request.node.name}")
    col_name = "MARKDOWN"
    owner = get_oracle_owner(connection_params)

    # Ensure clean slate
    _drop_table_if_exists(cur, table_name)

    # Create table and insert rows
    cur.execute(f"CREATE TABLE {table_name} ({col_name} CLOB)")
    cur.execute(f"INSERT INTO {table_name} ({col_name}) VALUES (:1)", ["row1"])  # noqa: S608
    cur.execute(f"INSERT INTO {table_name} ({col_name}) VALUES (:1)", ["row2"])  # noqa: S608
    connection.commit()

    try:
        component = OracleDocLoaderComponent().set(
            **get_oracle_connection_inputs(connection_params),
            params={
                "owner": owner,
                "tablename": table_name,
                "colname": col_name,
            },
        )

        data_list = component.load_documents()

        # Basic assertions
        assert isinstance(data_list, list)
        assert len(data_list) == 2
        assert all(isinstance(d, Data) for d in data_list)

        texts = {d.text for d in data_list}
        assert texts == {"row1", "row2"}

        # status updated
        assert component.status == data_list
    finally:
        # Cleanup the table
        _drop_table_if_exists(cur, table_name)
        connection.commit()


def test_oracle_doc_loader_component_empty_table(
    request,
    connection: oracledb.Connection | None,
    connection_params: dict[str, str] | None,
) -> None:
    """Integration test for OracleDocLoaderComponent with an empty table."""
    if not connection_params:
        with (
            patch(
                "lfx.components.oracledb.oracledb_loaders.oracledb.connect",
                return_value=MagicMock(),
            ) as mock_connect,
            patch("lfx.components.oracledb.oracledb_loaders.OracleDocLoader") as mock_loader,
        ):
            mock_loader.return_value.load.return_value = []
            test_connection_inputs = get_oracle_test_connection_inputs()
            component = OracleDocLoaderComponent().set(
                dsn=test_connection_inputs["dsn"],
                params={"owner": "mock_owner", "tablename": "MOCK_TABLE", "colname": "MARKDOWN"},
            )

            data_list = component.load_documents()

        assert isinstance(data_list, list)
        assert data_list == []
        assert component.status == []
        mock_connect.assert_called_once_with(dsn=test_connection_inputs["dsn"])
        mock_loader.assert_called_once()
        return

    assert connection is not None
    cur = connection.cursor()

    table_name = _safe_identifier(f"lfx_empty_{request.node.name}")
    col_name = "MARKDOWN"
    owner = get_oracle_owner(connection_params)

    _drop_table_if_exists(cur, table_name)
    cur.execute(f"CREATE TABLE {table_name} ({col_name} CLOB)")
    connection.commit()

    try:
        component = OracleDocLoaderComponent().set(
            **get_oracle_connection_inputs(connection_params),
            params={
                "owner": owner,
                "tablename": table_name,
                "colname": col_name,
            },
        )

        data_list = component.load_documents()
        assert isinstance(data_list, list)
        assert data_list == []
        assert component.status == []
    finally:
        _drop_table_if_exists(cur, table_name)
        connection.commit()


def test_oracle_autonomous_database_loader_component_load_documents(
    request,
    connection: oracledb.Connection | None,
    connection_params: dict[str, str] | None,
) -> None:
    if not connection_params:
        with patch("lfx.components.oracledb.oracledb_loaders.OracleAutonomousDatabaseLoader") as mock_loader:
            mock_loader.return_value.load.return_value = _adb_expected_documents()
            test_connection_inputs = get_oracle_test_connection_inputs()
            component = OracleAutonomousDatabaseLoaderComponent().set(
                query="select * from test_table",
                **test_connection_inputs,
                metadata="FIELD1",
            )

            data_list = component.load_documents()

        assert [data.text for data in data_list] == [doc.page_content for doc in _adb_expected_documents()]
        assert [data.data["FIELD1"] for data in data_list] == ["1", "2", "3"]
        assert component.status == data_list
        mock_loader.assert_called_once()
        assert mock_loader.call_args.kwargs == {
            "query": "select * from test_table",
            "user": test_connection_inputs["user"],
            "password": test_connection_inputs["password"],
            "schema": None,
            "dsn": test_connection_inputs["dsn"],
            "config_dir": None,
            "wallet_location": None,
            "wallet_password": None,
            "metadata": ["FIELD1"],
            "parameter": mock_loader.call_args.kwargs["parameter"],
        }
        assert mock_loader.call_args.kwargs["parameter"] in (None, {})
        return

    assert connection is not None
    cur = connection.cursor()
    table_name = _safe_identifier(f"adb_{request.node.name}")
    owner = get_oracle_owner(connection_params)

    _drop_table_if_exists(cur, table_name)
    cur.execute(f"CREATE TABLE {table_name} (FIELD1 VARCHAR2(10), FIELD_JSON CLOB)")
    cur.execute(
        f"INSERT INTO {table_name} (FIELD1, FIELD_JSON) VALUES (:1, :2)",  # noqa: S608
        ["1", "{'INNER_FIELD1': '1', 'INNER_FIELD2': '1'}"],
    )
    cur.execute(
        f"INSERT INTO {table_name} (FIELD1, FIELD_JSON) VALUES (:1, :2)",  # noqa: S608
        ["2", "{'INNER_FIELD1': '2', 'INNER_FIELD2': '2'}"],
    )
    connection.commit()

    try:
        component = OracleAutonomousDatabaseLoaderComponent().set(
            query=f"SELECT FIELD1, FIELD_JSON FROM {owner}.{table_name} ORDER BY FIELD1",  # noqa: S608
            **get_oracle_connection_inputs(connection_params),
            metadata="FIELD1",
        )

        data_list = component.load_documents()

        assert len(data_list) == 2
        assert [data.data["FIELD1"] for data in data_list] == ["1", "2"]
        assert "FIELD_JSON" in data_list[0].text
        assert component.status == data_list
    finally:
        _drop_table_if_exists(cur, table_name)
        connection.commit()


def test_oracle_autonomous_database_loader_component_maps_aliases_and_optional_args() -> None:
    with patch("lfx.components.oracledb.oracledb_loaders.OracleAutonomousDatabaseLoader") as mock_loader:
        mock_loader.return_value.load.return_value = []
        test_connection_inputs = get_oracle_test_connection_inputs(include_wallet_password=True)
        component = OracleAutonomousDatabaseLoaderComponent().set(
            query="select * from my_table where id = :id",
            **test_connection_inputs,
            connection_params={
                "config_dir": "/wallet/config",
                "wallet_location": "/wallet",
                "schema": "MY_SCHEMA",
            },
            metadata="FIELD1, FIELD2",
            parameter={"id": 7},
        )

        data_list = component.load_documents()

    assert data_list == []
    assert component.status == []
    mock_loader.assert_called_once_with(
        query="select * from my_table where id = :id",
        user=test_connection_inputs["user"],
        password=test_connection_inputs["password"],
        schema="MY_SCHEMA",
        dsn=test_connection_inputs["dsn"],
        config_dir="/wallet/config",
        wallet_location="/wallet",
        wallet_password=test_connection_inputs["wallet_password"],
        metadata=["FIELD1", "FIELD2"],
        parameter={"id": 7},
    )


def test_oracle_autonomous_database_loader_component_rejects_sensitive_connection_params() -> None:
    test_connection_inputs = get_oracle_test_connection_inputs(include_wallet_password=True)
    component = OracleAutonomousDatabaseLoaderComponent().set(
        query="select * from my_table",
        **test_connection_inputs,
        connection_params={
            "access_token": (test_connection_inputs["user"], test_connection_inputs["wallet_password"]),
            "private_key": test_connection_inputs["wallet_password"],
        },
    )

    with pytest.raises(
        ValueError,
        match="connection_params contains sensitive keys: access_token, private_key\\. Use the dedicated secret fields",
    ):
        component.load_documents()


def test_oracle_autonomous_database_loader_component_parses_credentials_from_dsn() -> None:
    with patch("lfx.components.oracledb.oracledb_loaders.OracleAutonomousDatabaseLoader") as mock_loader:
        mock_loader.return_value.load.return_value = []
        test_connection_inputs = get_oracle_test_connection_inputs()
        component = OracleAutonomousDatabaseLoaderComponent().set(
            query="select * from my_table",
            dsn=(
                f"{test_connection_inputs['user']}/{test_connection_inputs['password']}@{test_connection_inputs['dsn']}"
            ),
            metadata="FIELD1",
        )

        data_list = component.load_documents()

    assert data_list == []
    assert component.status == []
    mock_loader.assert_called_once()
    assert mock_loader.call_args.kwargs == {
        "query": "select * from my_table",
        "user": test_connection_inputs["user"],
        "password": test_connection_inputs["password"],
        "schema": None,
        "dsn": test_connection_inputs["dsn"],
        "config_dir": None,
        "wallet_location": None,
        "wallet_password": None,
        "metadata": ["FIELD1"],
        "parameter": mock_loader.call_args.kwargs["parameter"],
    }
    assert mock_loader.call_args.kwargs["parameter"] in (None, {})


def test_oracle_autonomous_database_loader_component_requires_user_and_password() -> None:
    test_connection_inputs = get_oracle_test_connection_inputs()
    component = OracleAutonomousDatabaseLoaderComponent().set(
        query="select * from my_table",
        dsn=test_connection_inputs["dsn"],
    )

    with pytest.raises(
        ValueError,
        match="Connection settings must include user and password, either in the dedicated fields or inside the DSN\\.",
    ):
        component.load_documents()
