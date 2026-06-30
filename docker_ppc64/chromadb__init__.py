from typing import Dict, Optional, Union
import logging
from chromadb.api.client import Client as ClientCreator
from chromadb.api.client import (
    AdminClient as AdminClientCreator,
)
from chromadb.api.async_client import AsyncClient as AsyncClientCreator
from chromadb.auth.token_authn import TokenTransportHeader
import chromadb.config
from chromadb.config import DEFAULT_DATABASE, DEFAULT_TENANT, Settings
from chromadb.api import AdminAPI, AsyncClientAPI, ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.api.types import (
    Cmek,
    CollectionMetadata,
    UpdateMetadata,
    Documents,
    EmbeddingFunction,
    Embeddings,
    URI,
    URIs,
    IDs,
    Include,
    Metadata,
    Metadatas,
    ReadLevel,
    Where,
    QueryResult,
    GetResult,
    WhereDocument,
    UpdateCollectionMetadata,
    SparseVector,
    SparseVectors,
    SparseEmbeddingFunction,
    Schema,
    VectorIndexConfig,
    HnswIndexConfig,
    SpannIndexConfig,
    FtsIndexConfig,
    SparseVectorIndexConfig,
    StringInvertedIndexConfig,
    IntInvertedIndexConfig,
    FloatInvertedIndexConfig,
    BoolInvertedIndexConfig,
)

# Import Search API components
from chromadb.execution.expression.plan import Search
from chromadb.execution.expression.operator import (
    # Key builder for where conditions and field selection
    Key,
    K,  # Alias for Key
    # KNN-based ranking for hybrid search
    Knn,
    # Reciprocal Rank Fusion for combining rankings
    Rrf,
)
from pathlib import Path
import os

# Re-export types from chromadb.types
__all__ = [
    "Cmek",
    "Collection",
    "Metadata",
    "Metadatas",
    "Where",
    "WhereDocument",
    "Documents",
    "IDs",
    "URI",
    "URIs",
    "Embeddings",
    "EmbeddingFunction",
    "Include",
    "CollectionMetadata",
    "UpdateMetadata",
    "UpdateCollectionMetadata",
    "QueryResult",
    "GetResult",
    "TokenTransportHeader",
    # Search API components
    "Search",
    "Key",
    "K",
    "Knn",
    "Rrf",
    # Sparse Vector Types
    "SparseVector",
    "SparseVectors",
    "SparseEmbeddingFunction",
    # Schema and Index Configuration
    "Schema",
    "VectorIndexConfig",
    "HnswIndexConfig",
    "SpannIndexConfig",
    "FtsIndexConfig",
    "SparseVectorIndexConfig",
    "StringInvertedIndexConfig",
    "IntInvertedIndexConfig",
    "FloatInvertedIndexConfig",
    "BoolInvertedIndexConfig",
]

from chromadb.types import CloudClientArg

logger = logging.getLogger(__name__)

__settings = Settings()

__version__ = "1.5.7"


# Workaround to deal with Colab's old sqlite3 version
def is_in_colab() -> bool:
    try:
        import google.colab  # noqa: F401

        return True
    except ImportError:
        return False


IN_COLAB = is_in_colab()

is_client = False
try:
    from chromadb.is_thin_client import is_thin_client

    is_client = is_thin_client
except ImportError:
    is_client = False

IN_COLAB = True
if not is_client:
    import sqlite3

    if sqlite3.sqlite_version_info < (3, 35, 0):
        if IN_COLAB:
            # In Colab, hotswap to pysqlite-binary if it's too old
            import subprocess
            import sys

            #subprocess.check_call(
            #    [sys.executable, "-m", "pip", "install", "pysqlite3-binary"]
            #)
            __import__("pysqlite3")
            sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
        else:
            raise RuntimeError(
                "\033[91mYour system has an unsupported version of sqlite3. Chroma \
                    requires sqlite3 >= 3.35.0.\033[0m\n"
                "\033[94mPlease visit \
                    https://docs.trychroma.com/troubleshooting#sqlite to learn how \
                    to upgrade.\033[0m"
            )


def configure(**kwargs) -> None:  # type: ignore
    """Override Chroma's default settings, environment variables or .env files"""
    global __settings
    __settings = chromadb.config.Settings(**kwargs)


def get_settings() -> Settings:
    return __settings


def EphemeralClient(
    settings: Optional[Settings] = None,
    tenant: str = DEFAULT_TENANT,
    database: str = DEFAULT_DATABASE,
) -> ClientAPI:
    """Create an in-memory client for local use.

    This client stores all data in memory and does not persist to disk.
    It is intended for testing and development.

    Args:
        settings: Optional settings to override defaults.
        tenant: Tenant name to use for requests. Defaults to the default tenant.
        database: Database name to use for requests. Defaults to the default database.

    Returns:
        ClientAPI: A configured client instance.
    """
    if settings is None:
        settings = Settings()
    settings.is_persistent = False

    # Make sure paramaters are the correct types -- users can pass anything.
    tenant = str(tenant)
    database = str(database)

    return ClientCreator(settings=settings, tenant=tenant, database=database)


def PersistentClient(
    path: Union[str, Path] = "./chroma",
    settings: Optional[Settings] = None,
    tenant: str = DEFAULT_TENANT,
    database: str = DEFAULT_DATABASE,
) -> ClientAPI:
    """Create a persistent client that stores data on disk.

    This client is intended for local development and testing. For production,
    prefer a server-backed Chroma instance.

    Args:
        path: Directory to store persisted data.
        settings: Optional settings to override defaults.
        tenant: Tenant name to use for requests.
        database: Database name to use for requests.

    Returns:
        ClientAPI: A configured client instance.
    """
    if settings is None:
        settings = Settings()
    settings.persist_directory = str(path)
    settings.is_persistent = True

    # Make sure paramaters are the correct types -- users can pass anything.
    tenant = str(tenant)
    database = str(database)

    return ClientCreator(tenant=tenant, database=database, settings=settings)


def RustClient(
    path: Optional[str] = None,
    settings: Optional[Settings] = None,
    tenant: str = DEFAULT_TENANT,
    database: str = DEFAULT_DATABASE,
) -> ClientAPI:
    """
    Creates an ephemeral or persistance instance of Chroma that saves to disk.
    This is useful for testing and development, but not recommended for production use.

    Args:
        path: An optional directory to save Chroma's data to. The client is ephemeral if a None value is provided. Defaults to None.
        tenant: The tenant to use for this client.
        database: The database to use for this client.
    """
    if settings is None:
        settings = Settings()

    settings.chroma_api_impl = "chromadb.api.rust.RustBindingsAPI"
    settings.is_persistent = path is not None
    settings.persist_directory = path or ""

    # Make sure paramaters are the correct types -- users can pass anything.
    tenant = str(tenant)
    database = str(database)

    return ClientCreator(tenant=tenant, database=database, settings=settings)


def HttpClient(
    host: str = "localhost",
    port: int = 8000,
    ssl: bool = False,
    headers: Optional[Dict[str, str]] = None,
    settings: Optional[Settings] = None,
    tenant: str = DEFAULT_TENANT,
    database: str = DEFAULT_DATABASE,
) -> ClientAPI:
    """Create a client that connects to a Chroma server.

    Args:
        host: Hostname of the Chroma server.
        port: HTTP port of the Chroma server.
        ssl: Whether to enable SSL for the connection.
        headers: Optional headers to send with each request.
        settings: Optional settings to override defaults.
        tenant: Tenant name to use for requests.
        database: Database name to use for requests.

    Returns:
        ClientAPI: A configured client instance.

    Raises:
        ValueError: If settings specify a different host or port.
    """

    if settings is None:
        settings = Settings()

    # Make sure parameters are the correct types -- users can pass anything.
    host = str(host)
    port = int(port)
    ssl = bool(ssl)
    tenant = str(tenant)
    database = str(database)

    settings.chroma_api_impl = "chromadb.api.fastapi.FastAPI"
    if settings.chroma_server_host and settings.chroma_server_host != host:
        raise ValueError(
            f"Chroma server host provided in settings[{settings.chroma_server_host}] is different to the one provided in HttpClient: [{host}]"
        )
    settings.chroma_server_host = host
    if settings.chroma_server_http_port and settings.chroma_server_http_port != port:
        raise ValueError(
            f"Chroma server http port provided in settings[{settings.chroma_server_http_port}] is different to the one provided in HttpClient: [{port}]"
        )
    settings.chroma_server_http_port = port
    settings.chroma_server_ssl_enabled = ssl
    settings.chroma_server_headers = headers

    return ClientCreator(tenant=tenant, database=database, settings=settings)


async def AsyncHttpClient(
    host: str = "localhost",
    port: int = 8000,
    ssl: bool = False,
    headers: Optional[Dict[str, str]] = None,
    settings: Optional[Settings] = None,
    tenant: str = DEFAULT_TENANT,
    database: str = DEFAULT_DATABASE,
) -> AsyncClientAPI:
    """Create an async client that connects to a Chroma HTTP server.

    This supports multiple clients connecting to the same server and is the
    recommended production configuration.

    Args:
        host: Hostname of the Chroma server.
        port: HTTP port of the Chroma server.
        ssl: Whether to enable SSL for the connection.
        headers: Optional headers to send with each request.
        settings: Optional settings to override defaults.
        tenant: Tenant name to use for requests.
        database: Database name to use for requests.

    Returns:
        AsyncClientAPI: A configured async client instance.

    Raises:
        ValueError: If settings specify a different host or port.
    """

    if settings is None:
        settings = Settings()

    # Make sure parameters are the correct types -- users can pass anything.
    host = str(host)
    port = int(port)
    ssl = bool(ssl)
    tenant = str(tenant)
    database = str(database)

    settings.chroma_api_impl = "chromadb.api.async_fastapi.AsyncFastAPI"
    if settings.chroma_server_host and settings.chroma_server_host != host:
        raise ValueError(
            f"Chroma server host provided in settings[{settings.chroma_server_host}] is different to the one provided in HttpClient: [{host}]"
        )
    settings.chroma_server_host = host
    if settings.chroma_server_http_port and settings.chroma_server_http_port != port:
        raise ValueError(
            f"Chroma server http port provided in settings[{settings.chroma_server_http_port}] is different to the one provided in HttpClient: [{port}]"
        )
    settings.chroma_server_http_port = port
    settings.chroma_server_ssl_enabled = ssl
    settings.chroma_server_headers = headers

    return await AsyncClientCreator.create(
        tenant=tenant, database=database, settings=settings
    )


def CloudClient(
    tenant: Optional[str] = None,
    database: Optional[str] = None,
    api_key: Optional[str] = None,
    settings: Optional[Settings] = None,
    *,  # Following arguments are keyword-only, intended for testing only.
    cloud_host: str = "api.trychroma.com",
    cloud_port: int = 443,
    enable_ssl: bool = True,
) -> ClientAPI:
    """Create a client for Chroma Cloud.

    If not provided, `tenant`, `database`, and `api_key` will be inferred from the environment variables `CHROMA_TENANT`, `CHROMA_DATABASE`, and `CHROMA_API_KEY`.

    Args:
        tenant: Tenant name to use, or None to infer from credentials.
        database: Database name to use, or None to infer from credentials.
        api_key: API key for Chroma Cloud.
        settings: Optional settings to override defaults.

    Returns:
        ClientAPI: A configured client instance.

    Raises:
        ValueError: If no API key is provided or available in the environment.
    """

    required_args = [
        CloudClientArg(name="api_key", env_var="CHROMA_API_KEY", value=api_key),
    ]

    # If api_key is not provided, try to load it from the environment variable
    if not all([arg.value for arg in required_args]):
        for arg in required_args:
            arg.value = arg.value or os.environ.get(arg.env_var)

    missing_args = [arg for arg in required_args if arg.value is None]
    if missing_args:
        raise ValueError(
            f"Missing required arguments: {', '.join([arg.name for arg in missing_args])}. "
            f"Please provide them or set the environment variables: {', '.join([arg.env_var for arg in missing_args])}"
        )

    if settings is None:
        settings = Settings()

    # Make sure paramaters are the correct types -- users can pass anything.
    tenant = tenant or os.environ.get("CHROMA_TENANT")
    if tenant is not None:
        tenant = str(tenant)
    database = database or os.environ.get("CHROMA_DATABASE")
    if database is not None:
        database = str(database)
    api_key = str(api_key)
    cloud_host = str(cloud_host)
    cloud_port = int(cloud_port)
    enable_ssl = bool(enable_ssl)

    settings.chroma_api_impl = "chromadb.api.fastapi.FastAPI"
    settings.chroma_server_host = cloud_host
    settings.chroma_server_http_port = cloud_port
    settings.chroma_server_ssl_enabled = enable_ssl

    settings.chroma_client_auth_provider = (
        "chromadb.auth.token_authn.TokenAuthClientProvider"
    )
    settings.chroma_client_auth_credentials = api_key
    settings.chroma_auth_token_transport_header = TokenTransportHeader.X_CHROMA_TOKEN
    settings.chroma_overwrite_singleton_tenant_database_access_from_auth = True

    return ClientCreator(tenant=tenant, database=database, settings=settings)


def Client(
    settings: Settings = __settings,
    tenant: str = DEFAULT_TENANT,
    database: str = DEFAULT_DATABASE,
) -> ClientAPI:
    """
    Return a running chroma.API instance

    tenant: The tenant to use for this client. Defaults to the default tenant.
    database: The database to use for this client. Defaults to the default database.
    """

    # Make sure paramaters are the correct types -- users can pass anything.
    tenant = str(tenant)
    database = str(database)

    return ClientCreator(tenant=tenant, database=database, settings=settings)


def AdminClient(settings: Settings = Settings()) -> AdminAPI:
    """Create an admin client for tenant and database management."""
    return AdminClientCreator(settings=settings)
