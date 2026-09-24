"""Positive SSRF-block regression tests for connector components with a tenant-controlled host.

These prove the SSRF guards added to the model-provider discovery fetches and the Glean tool
actually block an internal/metadata host BEFORE any outbound request is made. The only thing
mocked is the settings service (to turn SSRF protection on) and the network sink (as a sentinel
to assert it is never reached) — the real SSRF validation logic runs.

The vector-store connector guards (qdrant/elasticsearch/opensearch/milvus/supabase/
upstash/clickhouse/chroma) and astradb_cql use the shared connector SSRF validators, which are
exercised directly in ``lfx/tests/unit/utils/test_ssrf_protection.py``. The weaviate, redis chat
memory, confluence, nvidia, and sambanova guards (H1-3996328) are exercised below.
"""

import sys
from contextlib import contextmanager
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")

METADATA_URL = "http://169.254.169.254"


@contextmanager
def ssrf_enabled():
    """Enable global and connector SSRF protection."""
    with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get:
        s = MagicMock()
        s.settings.ssrf_protection_enabled = True
        s.settings.connector_ssrf_validation_enabled = True
        s.settings.ssrf_allowed_hosts = []
        s.settings.restrict_local_file_access = False
        mock_get.return_value = s
        yield


def test_deepseek_get_models_blocks_metadata_without_request():
    """Deepseek returns its default model list on block — and never hits the host."""
    from lfx.components.deepseek.deepseek import DEEPSEEK_MODELS, DeepSeekModelComponent

    component = DeepSeekModelComponent()
    component.api_key = "test-key"  # required, else get_models early-returns without fetching
    component.api_base = METADATA_URL
    with ssrf_enabled(), patch("httpx.Client.get") as mock_get:
        result = component.get_models()
        assert mock_get.call_count == 0
        assert result == DEEPSEEK_MODELS


def test_xai_get_models_blocks_metadata_without_request():
    from lfx.components.xai.xai import XAI_DEFAULT_MODELS, XAIModelComponent

    component = XAIModelComponent()
    component.api_key = "test-key"
    component.base_url = METADATA_URL
    with ssrf_enabled(), patch("httpx.Client.get") as mock_get:
        result = component.get_models()
        assert mock_get.call_count == 0
        assert result == XAI_DEFAULT_MODELS


def test_litellm_proxy_blocks_metadata_without_request():
    """Litellm raises (ValueError) on block, before the httpx request."""
    from lfx.components.litellm.litellm_proxy import LiteLLMProxyComponent

    component = LiteLLMProxyComponent()
    component.api_base = METADATA_URL
    with (
        ssrf_enabled(),
        patch("httpx.Client.get") as mock_get,
        pytest.raises(ValueError, match="SSRF"),
    ):
        component._validate_proxy_connection("test-key")
    assert mock_get.call_count == 0


def test_huggingface_inference_endpoint_blocks_metadata_without_request():
    from lfx.components.huggingface.huggingface_inference_api import HuggingFaceInferenceAPIEmbeddingsComponent

    component = HuggingFaceInferenceAPIEmbeddingsComponent()
    component.inference_endpoint = METADATA_URL
    with (
        ssrf_enabled(),
        patch("httpx.Client.get") as mock_get,
        pytest.raises(ValueError, match="SSRF"),
    ):
        component.validate_inference_endpoint(METADATA_URL)
    assert mock_get.call_count == 0


def test_glean_blocks_metadata_before_token_sent():
    """Glean raises before the bearer token is attached to a request to a blocked host."""
    from lfx.components.glean.glean_search_api import GleanAPIWrapper
    from lfx.utils.ssrf_protection import SSRFProtectionError

    wrapper = GleanAPIWrapper(glean_api_url=METADATA_URL, glean_access_token="secret-token")  # noqa: S106 - test token
    with ssrf_enabled(), patch("httpx.Client.post") as mock_post, pytest.raises(SSRFProtectionError):
        wrapper._search_api_results("query")
    assert mock_post.call_count == 0


# H1-3996328: connectors that read a tenant-controlled URL/host and connected without ever
# calling the central SSRF guard. Each test pins the guard: the block must come from
# validate_connector_url_for_ssrf and the SDK sink must never be reached.


def test_weaviate_blocks_metadata_url_before_client_connect():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.weaviate.weaviate import WeaviateVectorStoreComponent

    component = WeaviateVectorStoreComponent(url=f"{METADATA_URL}:8080", index_name="Test")
    with ssrf_enabled(), patch("weaviate.connect_to_custom") as mock_connect, pytest.raises(SSRFProtectionError):
        component._connect_client()
    assert mock_connect.call_count == 0


def test_weaviate_blocks_metadata_grpc_host_before_client_connect():
    """A public-looking URL with a tenant-controlled internal grpc_host is still blocked."""
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.weaviate.weaviate import WeaviateVectorStoreComponent

    component = WeaviateVectorStoreComponent(
        url="http://localhost:8080", index_name="Test", grpc_host="169.254.169.254"
    )
    with ssrf_enabled(), patch("weaviate.connect_to_custom") as mock_connect, pytest.raises(SSRFProtectionError):
        component._connect_client()
    assert mock_connect.call_count == 0


def test_redis_chat_memory_blocks_metadata_host_before_connect():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.redis.redis_chat import RedisIndexChatMemory

    component = RedisIndexChatMemory()
    component.host = "169.254.169.254"
    component.port = 6379
    component.database = "0"
    component.username = ""
    component.password = ""
    component.key_prefix = ""
    component.session_id = "test-session"
    with (
        ssrf_enabled(),
        patch("lfx_bundles.redis.redis_chat.RedisChatMessageHistory") as mock_history,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_message_history()
    assert mock_history.call_count == 0


def test_confluence_blocks_metadata_url_before_loader():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.confluence.confluence import ConfluenceComponent

    component = ConfluenceComponent()
    component.url = f"{METADATA_URL}/wiki"
    component.username = "user@example.com"
    component.api_key = "test-key"
    component.space_key = "SPACE"
    component.cloud = True
    component.content_format = "storage"
    component.max_pages = 10
    with (
        ssrf_enabled(),
        patch("lfx_bundles.confluence.confluence.ConfluenceLoader") as mock_loader,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_confluence()
    assert mock_loader.call_count == 0


def test_nvidia_build_model_blocks_metadata_url_before_sdk():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

    component = NVIDIAModelComponent()
    component._attributes = {
        "base_url": f"{METADATA_URL}/v1",
        "api_key": "test-key",  # pragma: allowlist secret
        "model_name": "model",
        "max_tokens": 1,
        "temperature": 0.1,
        "seed": 1,
    }
    with ssrf_enabled(), pytest.raises(SSRFProtectionError):
        component.build_model()


def test_nvidia_get_models_blocks_metadata_url_before_sdk():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.nvidia.nvidia import NVIDIAModelComponent

    component = NVIDIAModelComponent()
    component._attributes = {
        "base_url": f"{METADATA_URL}/v1",
        "api_key": "test-key",  # pragma: allowlist secret
        "tool_model_enabled": False,
    }
    with ssrf_enabled(), pytest.raises(SSRFProtectionError):
        component.get_models()


def test_sambanova_build_model_blocks_metadata_url_before_sdk():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.sambanova.sambanova import SambaNovaComponent

    component = SambaNovaComponent()
    component.base_url = f"{METADATA_URL}/v1/chat/completions"
    component.model_name = "Meta-Llama-3.1-8B-Instruct"
    component.api_key = "test-key"
    component.max_tokens = 16
    component.top_p = 1.0
    component.temperature = 0.1
    with (
        ssrf_enabled(),
        patch("lfx_bundles.sambanova.sambanova.ChatSambaNovaCloud") as mock_chat,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_model()
    assert mock_chat.call_count == 0


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://169.254.169.254:27017/test",
        "mongodb://8.8.8.8:27017,169.254.169.254:27017/test",
        "mongodb+srv://169.254.169.254/test",
    ],
)
def test_mongodb_blocks_every_seed_before_client_connect(uri):
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.mongodb.mongodb_atlas import MongoVectorStoreComponent

    component = MongoVectorStoreComponent()
    component.mongodb_atlas_cluster_uri = uri
    with ssrf_enabled(), patch("pymongo.MongoClient") as mock_client, pytest.raises(SSRFProtectionError):
        component.build_vector_store()
    mock_client.assert_not_called()


def test_mongodb_preserves_public_seed_connection():
    from lfx_bundles.mongodb.mongodb_atlas import MongoVectorStoreComponent

    component = MongoVectorStoreComponent()
    component.mongodb_atlas_cluster_uri = "mongodb://8.8.8.8:27017/test"
    component.enable_mtls = False
    component.db_name = "db"
    component.collection_name = "docs"
    component.index_name = "vector"
    component.embedding = MagicMock()
    component.ingest_data = []
    with (
        ssrf_enabled(),
        patch("pymongo.MongoClient") as mock_client,
        patch("lfx_bundles.mongodb.mongodb_atlas.MongoDBAtlasVectorSearch") as mock_store,
    ):
        assert component.build_vector_store() is mock_store.return_value
    mock_client.assert_called_once_with(component.mongodb_atlas_cluster_uri)


def test_mongodb_unix_socket_follows_loopback_setting():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.mongodb.mongodb_atlas import MongoVectorStoreComponent

    component = MongoVectorStoreComponent()
    component.mongodb_atlas_cluster_uri = "mongodb://%2Ftmp%2Fmongodb-27017.sock"
    component.enable_mtls = False
    component.db_name = "db"
    component.collection_name = "docs"
    component.index_name = "vector"
    component.embedding = MagicMock()
    component.ingest_data = []
    with (
        ssrf_enabled(),
        patch("lfx_bundles.mongodb.mongodb_atlas.is_connector_loopback_allowed", return_value=False),
        patch("pymongo.MongoClient") as mock_client,
        pytest.raises(SSRFProtectionError, match="Unix sockets"),
    ):
        component.build_vector_store()
    mock_client.assert_not_called()

    with (
        ssrf_enabled(),
        patch("lfx_bundles.mongodb.mongodb_atlas.is_connector_loopback_allowed", return_value=True),
        patch("pymongo.MongoClient") as mock_client,
        patch("lfx_bundles.mongodb.mongodb_atlas.MongoDBAtlasVectorSearch") as mock_store,
    ):
        assert component.build_vector_store() is mock_store.return_value
    mock_client.assert_called_once_with(component.mongodb_atlas_cluster_uri)


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://8.8.8.8/?tlsCAFile=/tmp/nonexistent.pem",
        "mongodb://8.8.8.8/?tlsCertificateKeyFile=/tmp/nonexistent.pem",
        "mongodb://8.8.8.8/?tlsCRLFile=/tmp/nonexistent.pem",
        "mongodb://8.8.8.8#x:pw@8.8.4.4/db?tlsCAFile=/tmp/nonexistent.pem",
        "mongodb://8.8.8.8/?retryWrites=true;tlsCAFile=/tmp/nonexistent.pem",
    ],
)
def test_mongodb_rejects_uri_tls_files_before_parser_opens_them(uri):
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.mongodb.mongodb_atlas import MongoVectorStoreComponent

    component = MongoVectorStoreComponent()
    component.mongodb_atlas_cluster_uri = uri
    with (
        patch("lfx_bundles.mongodb.mongodb_atlas.is_local_file_access_restricted", return_value=True),
        patch("pymongo.uri_parser.parse_uri") as mock_parse,
        patch("pymongo.MongoClient") as mock_client,
        pytest.raises(SSRFProtectionError, match="local filesystem"),
    ):
        component.build_vector_store()
    mock_parse.assert_not_called()
    mock_client.assert_not_called()


def test_mongodb_blocks_internal_srv_target_before_client_connect():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.mongodb.mongodb_atlas import MongoVectorStoreComponent

    component = MongoVectorStoreComponent()
    component.mongodb_atlas_cluster_uri = "mongodb+srv://8.8.8.8/test"
    with (
        ssrf_enabled(),
        patch("pymongo.uri_parser.parse_uri", return_value={"nodelist": [("169.254.169.254", 27017)]}),
        patch("pymongo.MongoClient") as mock_client,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_vector_store()
    mock_client.assert_not_called()


def test_mongodb_srv_seed_does_not_require_address_record():
    from lfx_bundles.mongodb.mongodb_atlas import MongoVectorStoreComponent

    component = MongoVectorStoreComponent()
    component.mongodb_atlas_cluster_uri = "mongodb+srv://cluster.example.com/test"
    component.enable_mtls = False
    component.db_name = "db"
    component.collection_name = "docs"
    component.index_name = "vector"
    component.embedding = MagicMock()
    component.ingest_data = []
    with (
        ssrf_enabled(),
        patch("pymongo.uri_parser.parse_uri", return_value={"nodelist": [("8.8.8.8", 27017)]}),
        patch("lfx.utils.ssrf_protection.resolve_hostname", side_effect=AssertionError("seed A lookup")),
        patch("pymongo.MongoClient"),
        patch("lfx_bundles.mongodb.mongodb_atlas.MongoDBAtlasVectorSearch") as mock_store,
    ):
        assert component.build_vector_store() is mock_store.return_value


@pytest.mark.parametrize(
    "uri",
    [
        "redis://user:password@169.254.169.254:6379/0",  # pragma: allowlist secret
        "redis://?host=169.254.169.254",
    ],
)
def test_redis_vector_store_blocks_effective_host_before_sdk(uri):
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.redis.redis import RedisVectorStoreComponent

    component = RedisVectorStoreComponent()
    component.redis_server_url = uri
    with (
        ssrf_enabled(),
        patch("lfx_bundles.redis.redis.Redis.from_existing_index") as mock_connect,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_vector_store()
    mock_connect.assert_not_called()


def test_redis_vector_store_preserves_public_connection():
    from lfx_bundles.redis.redis import RedisVectorStoreComponent

    component = RedisVectorStoreComponent()
    component.redis_server_url = "redis://8.8.8.8:6379/0"
    component.redis_index_name = "docs"
    component.schema = "schema"
    component.embedding = MagicMock()
    component.ingest_data = []
    with (
        ssrf_enabled(),
        patch("lfx_bundles.redis.redis.Path.write_text"),
        patch("lfx_bundles.redis.redis.Redis.from_existing_index") as mock_connect,
    ):
        assert component.build_vector_store() is mock_connect.return_value
    assert mock_connect.call_args.kwargs["redis_url"] == component.redis_server_url


def test_redis_vector_store_preserves_unix_socket_connection():
    from lfx_bundles.redis.redis import RedisVectorStoreComponent

    component = RedisVectorStoreComponent()
    component.redis_server_url = "unix:///tmp/redis.sock"
    component.redis_index_name = "docs"
    component.schema = "schema"
    component.embedding = MagicMock()
    component.ingest_data = []
    with (
        ssrf_enabled(),
        patch("lfx_bundles.redis.redis.Path.write_text"),
        patch("lfx_bundles.redis.redis.Redis.from_existing_index") as mock_connect,
    ):
        assert component.build_vector_store() is mock_connect.return_value
    assert mock_connect.call_args.kwargs["redis_url"] == component.redis_server_url


def test_redis_vector_store_blocks_unix_socket_when_loopback_disabled():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.redis.redis import RedisVectorStoreComponent

    component = RedisVectorStoreComponent()
    component.redis_server_url = "unix:///tmp/redis.sock"
    with (
        ssrf_enabled(),
        patch("lfx_bundles.redis.redis.is_connector_loopback_allowed", return_value=False),
        patch("lfx_bundles.redis.redis.Redis.from_existing_index") as mock_connect,
        pytest.raises(SSRFProtectionError, match="Unix sockets"),
    ):
        component.build_vector_store()
    mock_connect.assert_not_called()


@pytest.mark.parametrize("scheme", ["redis+sentinel", "rediss+sentinel"])
def test_redis_vector_store_blocks_metadata_sentinel_before_sdk(scheme):
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.redis.redis import RedisVectorStoreComponent

    component = RedisVectorStoreComponent()
    component.redis_server_url = f"{scheme}://169.254.169.254:26379/mymaster/0"
    with (
        ssrf_enabled(),
        patch("lfx_bundles.redis.redis.Redis.from_existing_index") as mock_connect,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_vector_store()
    mock_connect.assert_not_called()


@pytest.mark.parametrize("scheme", ["redis+sentinel", "rediss+sentinel"])
def test_redis_vector_store_preserves_public_sentinel_connection(scheme):
    from lfx_bundles.redis.redis import RedisVectorStoreComponent

    component = RedisVectorStoreComponent()
    component.redis_server_url = f"{scheme}://8.8.8.8:26379/mymaster/0"
    component.redis_index_name = "docs"
    component.schema = "schema"
    component.embedding = MagicMock()
    component.ingest_data = []
    with (
        ssrf_enabled(),
        patch("lfx_bundles.redis.redis.Path.write_text"),
        patch("lfx_bundles.redis.redis.Redis.from_existing_index") as mock_connect,
    ):
        assert component.build_vector_store() is mock_connect.return_value
    assert mock_connect.call_args.kwargs["redis_url"] == component.redis_server_url


@pytest.mark.parametrize(
    "disabled_gate",
    ["is_connector_ssrf_validation_enabled", "is_ssrf_protection_enabled"],
)
def test_redis_vector_store_opted_out_sentinel_connection(disabled_gate):
    from lfx_bundles.redis.redis import RedisVectorStoreComponent

    component = RedisVectorStoreComponent()
    component.redis_server_url = "redis+sentinel://localhost:26379/mymaster/0"
    component.redis_index_name = "docs"
    component.schema = "schema"
    component.embedding = MagicMock()
    component.ingest_data = []
    with (
        patch(f"lfx_bundles.redis.redis.{disabled_gate}", return_value=False),
        patch("lfx_bundles.redis.redis.Path.write_text"),
        patch("lfx_bundles.redis.redis.Redis.from_existing_index") as mock_connect,
    ):
        assert component.build_vector_store() is mock_connect.return_value
    assert mock_connect.call_args.kwargs["redis_url"] == component.redis_server_url


@pytest.mark.parametrize(
    "uri",
    [
        "postgresql://user:password@169.254.169.254:5432/db",  # pragma: allowlist secret
        "postgresql://user:password@8.8.8.8:5432/db?hostaddr=169.254.169.254",  # pragma: allowlist secret
    ],
)
def test_pgvector_blocks_metadata_before_sdk(uri):
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.pgvector.pgvector import PGVectorStoreComponent

    component = PGVectorStoreComponent()
    component.pg_server_url = uri
    component.ingest_data = []
    with (
        ssrf_enabled(),
        patch("lfx_bundles.pgvector.pgvector.PGVector.from_existing_index") as mock_connect,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_vector_store()
    mock_connect.assert_not_called()


def test_pgvector_preserves_public_database_connection():
    from lfx_bundles.pgvector.pgvector import PGVectorStoreComponent

    component = PGVectorStoreComponent()
    component.pg_server_url = "postgresql://user:password@8.8.8.8:5432/db"  # pragma: allowlist secret
    component.collection_name = "docs"
    component.embedding = MagicMock()
    component.ingest_data = []
    with ssrf_enabled(), patch("lfx_bundles.pgvector.pgvector.PGVector.from_existing_index") as mock_connect:
        assert component.build_vector_store() is mock_connect.return_value
    assert mock_connect.call_args.kwargs["connection_string"] == component.pg_server_url


@pytest.mark.parametrize(
    "uri",
    [
        "postgresql://8.8.8.8?x:pw@169.254.169.254:5432/db",
        "postgresql://8.8.8.8#x:pw@169.254.169.254:5432/db",
    ],
)
def test_pgvector_blocks_sqlalchemy_username_delimiter_bypass(uri):
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.pgvector.pgvector import PGVectorStoreComponent

    component = PGVectorStoreComponent()
    component.pg_server_url = uri
    component.ingest_data = []
    with (
        ssrf_enabled(),
        patch("lfx_bundles.pgvector.pgvector.PGVector.from_existing_index") as mock_connect,
        pytest.raises(SSRFProtectionError),
    ):
        component.build_vector_store()
    mock_connect.assert_not_called()


def test_supabase_blocks_metadata_before_credentials_reach_sdk():
    from lfx.utils.ssrf_protection import SSRFProtectionError

    # The optional Supabase SDK is not needed to prove the guard runs before client creation.
    supabase = ModuleType("supabase")
    supabase.__path__ = []
    client = ModuleType("supabase.client")
    client.Client = MagicMock()
    client.create_client = MagicMock()
    supabase.client = client
    with patch.dict(sys.modules, {"supabase": supabase, "supabase.client": client}):
        from lfx_bundles.supabase.supabase import SupabaseVectorStoreComponent

        component = SupabaseVectorStoreComponent()
        component.supabase_url = METADATA_URL
        component.supabase_service_key = "test-key"
        with ssrf_enabled(), pytest.raises(SSRFProtectionError):
            component.build_vector_store()
        client.create_client.assert_not_called()

        component.supabase_url = "https://8.8.8.8"
        component.ingest_data = []
        component.embedding = MagicMock()
        component.table_name = "docs"
        component.query_name = "search"
        with ssrf_enabled(), patch("lfx_bundles.supabase.supabase.SupabaseVectorStore") as mock_store:
            assert component.build_vector_store() is mock_store.return_value
        client.create_client.assert_called_once_with(component.supabase_url, supabase_key="test-key")


@pytest.mark.parametrize("separator", [",", ";"])
def test_couchbase_blocks_second_seed_before_sdk_import(separator):
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.couchbase.couchbase import CouchbaseVectorStoreComponent

    component = CouchbaseVectorStoreComponent()
    component.couchbase_connection_string = f"couchbases://8.8.8.8{separator}169.254.169.254"
    with ssrf_enabled(), pytest.raises(SSRFProtectionError):
        component.build_vector_store()


def test_couchbase_allows_public_multi_seed_url():
    from lfx_bundles.couchbase.couchbase import _validate_couchbase_hosts

    with ssrf_enabled():
        _validate_couchbase_hosts("couchbases://8.8.8.8,1.1.1.1")


def test_couchbase_blocks_internal_srv_target():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.couchbase.couchbase import _validate_couchbase_hosts

    with (
        ssrf_enabled(),
        patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["8.8.8.8"]),
        patch("dns.resolver.resolve", return_value=[MagicMock(target="169.254.169.254.")]) as mock_resolve,
        pytest.raises(SSRFProtectionError),
    ):
        _validate_couchbase_hosts("couchbases://cluster.example.com")
    mock_resolve.assert_called_once_with("_couchbases._tcp.cluster.example.com", "SRV")


def test_couchbase_srv_seed_does_not_require_address_record():
    from lfx_bundles.couchbase.couchbase import _validate_couchbase_hosts

    with (
        ssrf_enabled(),
        patch("lfx.utils.ssrf_protection.resolve_hostname", side_effect=AssertionError("seed A lookup")),
        patch("dns.resolver.resolve", return_value=[MagicMock(target="8.8.8.8.")]),
    ):
        _validate_couchbase_hosts("couchbases://cluster.example.com")


def test_couchbase_blocks_internal_fallback_seed_when_srv_is_absent():
    import dns.resolver
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.couchbase.couchbase import _validate_couchbase_hosts

    with (
        ssrf_enabled(),
        patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["169.254.169.254"]),
        patch("dns.resolver.resolve", side_effect=dns.resolver.NoAnswer) as mock_srv,
        pytest.raises(SSRFProtectionError),
    ):
        _validate_couchbase_hosts("couchbases://cluster.example.com")
    mock_srv.assert_called_once_with("_couchbases._tcp.cluster.example.com", "SRV")


def test_couchbase_validates_explicit_port_seed_even_with_public_srv():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.couchbase.couchbase import _validate_couchbase_hosts

    with (
        ssrf_enabled(),
        patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["169.254.169.254"]),
        patch("dns.resolver.resolve", return_value=[MagicMock(target="8.8.8.8.")]) as mock_srv,
        pytest.raises(SSRFProtectionError),
    ):
        _validate_couchbase_hosts("couchbase://cluster.example.com:11210")
    mock_srv.assert_not_called()  # A blocked seed is rejected before discovery.


def test_couchbase_validates_explicit_port_srv_target():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.couchbase.couchbase import _validate_couchbase_hosts

    with (
        ssrf_enabled(),
        patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["8.8.8.8"]),
        patch("dns.resolver.resolve", return_value=[MagicMock(target="169.254.169.254.")]) as mock_srv,
        pytest.raises(SSRFProtectionError),
    ):
        _validate_couchbase_hosts("couchbase://cluster.example.com:11210")
    mock_srv.assert_called_once_with("_couchbase._tcp.cluster.example.com", "SRV")


@pytest.mark.parametrize("query", ["enable_dns_srv=false", "dns_nameserver=8.8.8.8"])
def test_couchbase_rejects_dns_discovery_overrides(query):
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.couchbase.couchbase import _validate_couchbase_hosts

    with ssrf_enabled(), pytest.raises(SSRFProtectionError, match="DNS discovery"):
        _validate_couchbase_hosts(f"couchbase://8.8.8.8?{query}")


def test_couchbase_rejects_trust_certificate_when_local_files_restricted():
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.couchbase.couchbase import _validate_couchbase_hosts

    with (
        patch("lfx_bundles.couchbase.couchbase.is_local_file_access_restricted", return_value=True),
        patch("lfx_bundles.couchbase.couchbase.is_connector_ssrf_validation_enabled", return_value=False),
        pytest.raises(SSRFProtectionError, match="local filesystem"),
    ):
        _validate_couchbase_hosts("couchbase://8.8.8.8?trust_certificate=/tmp/ca.pem")


@pytest.mark.parametrize(
    "url",
    [
        "couchbase://8.8.8.8?foo=bar;trust_certificate=/tmp/ca.pem",
        "couchbase://8.8.8.8#x?trust_certificate=/tmp/ca.pem",
    ],
)
def test_couchbase_rejects_ambiguous_certificate_options(url):
    from lfx.utils.ssrf_protection import SSRFProtectionError
    from lfx_bundles.couchbase.couchbase import _validate_couchbase_hosts

    with (
        patch("lfx_bundles.couchbase.couchbase.is_local_file_access_restricted", return_value=True),
        patch("lfx_bundles.couchbase.couchbase.is_connector_ssrf_validation_enabled", return_value=False),
        pytest.raises(SSRFProtectionError),
    ):
        _validate_couchbase_hosts(url)
