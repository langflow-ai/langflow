from contextlib import suppress

import oracledb
from langchain_oracledb import OracleEmbeddings

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import Embeddings
from lfx.io import DictInput, Output, SecretStrInput

from .connection import build_connection_params


class OracleEmbeddingsComponent(LCModelComponent):
    display_name = "Oracle Embeddings"
    description = "Generate embeddings using Oracle AI Vector Search."
    icon = "Oracle"
    name = "OracleEmbeddings"

    inputs = [
        SecretStrInput(name="user", display_name="User", required=False),
        SecretStrInput(name="password", display_name="Password", required=False),
        SecretStrInput(name="dsn", display_name="DSN", required=True),
        SecretStrInput(name="wallet_password", display_name="Wallet Password", required=False, advanced=True),
        DictInput(
            name="connection_params",
            display_name="Additional Connection Parameters",
            info="Non-secret arguments passed to python-oracledb connect(), such as config_dir and wallet_location.",
            list=True,
            required=False,
            advanced=True,
        ),
        DictInput(
            name="embedding_params",
            display_name="Embedding Parameters",
            list=True,
            info=(
                "https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/utl_to_embedding-and-utl_to_embeddings-dbms_vector.html"
            ),
        ),
        SecretStrInput(name="proxy", display_name="Proxy", required=False, advanced=True),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        connection_params = build_connection_params(
            self.connection_params,
            user=self.user,
            password=self.password,
            dsn=self.dsn,
            wallet_password=self.wallet_password,
        )
        connection = oracledb.connect(**connection_params)

        try:
            return OracleEmbeddings(
                conn=connection,
                params=self.embedding_params,
                proxy=self.proxy or None,
            )
        except Exception as e:
            with suppress(Exception):
                connection.close()
            msg = "Unable to create OracleEmbeddings."
            raise ValueError(msg) from e
