from datetime import timedelta
from ipaddress import ip_address
from urllib.parse import parse_qsl, urlsplit

import dns.exception
import dns.resolver
from langchain_community.vectorstores import CouchbaseVectorStore
from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import HandleInput, IntInput, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx.utils.file_path_security import is_local_file_access_restricted
from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_connector_ssrf_validation_enabled,
    is_ssrf_protection_enabled,
    validate_connector_hostname_for_ssrf,
)


def _validate_couchbase_hosts(connection_string: str) -> None:
    parsed = urlsplit(connection_string)
    file_restricted = is_local_file_access_restricted()
    ssrf_enabled = is_connector_ssrf_validation_enabled() and is_ssrf_protection_enabled()
    if parsed.fragment and (file_restricted or ssrf_enabled):
        msg = "Couchbase connection string fragments are not permitted."
        raise SSRFProtectionError(msg)
    query_keys = {key.casefold() for key, _value in parse_qsl(parsed.query.replace(";", "&"), keep_blank_values=True)}
    if file_restricted and "trust_certificate" in query_keys:
        msg = "Couchbase trust_certificate can access the local filesystem and is not permitted."
        raise SSRFProtectionError(msg)
    if not ssrf_enabled:
        return

    if parsed.scheme not in {"couchbase", "couchbases"} or not parsed.netloc:
        msg = "Couchbase connection string must contain a host."
        raise SSRFProtectionError(msg)

    # The C++ SDK can treat a semicolon as part of a DNS hostname, but as a
    # separator after an IP literal. Reject this ambiguous form outright.
    if ";" in parsed.netloc:
        msg = "Couchbase connection string host cannot contain a semicolon."
        raise SSRFProtectionError(msg)
    seeds = parsed.netloc.split(",")
    if query_keys & {"enable_dns_srv", "dns_nameserver"}:
        msg = "Couchbase connection string cannot override DNS discovery settings."
        raise SSRFProtectionError(msg)
    for seed in seeds:
        if not seed or any(char in seed for char in "@\\/%?#"):
            msg = "Couchbase connection string contains an invalid host."
            raise SSRFProtectionError(msg)
        try:
            address = urlsplit(f"//{seed}")
            host = address.hostname
            port = address.port  # Check for an invalid port before the SDK interprets the seed.
        except ValueError as e:
            msg = "Couchbase connection string contains an invalid host."
            raise SSRFProtectionError(msg) from e
        # An explicit port does not disable DNS SRV in the C++ SDK. Validate
        # that seed as a possible direct target, then inspect any SRV targets.
        # A portless single seed may have only SRV records and no A/AAAA record.
        seed_needs_validation = len(seeds) > 1 or port is not None
        if seed_needs_validation:
            validate_connector_hostname_for_ssrf(host or "")
        if len(seeds) == 1 and host:
            try:
                ip_address(host)
            except ValueError:
                try:
                    records = dns.resolver.resolve(f"_{parsed.scheme}._tcp.{host}", "SRV")
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                    pass  # The SDK falls back to the seed host when no SRV record exists.
                except dns.exception.DNSException as e:
                    msg = "Could not verify Couchbase bootstrap nodes."
                    raise SSRFProtectionError(msg) from e
                else:
                    if records:
                        for record in records:
                            validate_connector_hostname_for_ssrf(str(record.target).rstrip("."))
                        continue
        # The SDK falls back to this seed when SRV is absent. Multi-seed and
        # explicit-port seeds were already checked as possible direct targets.
        if not seed_needs_validation:
            validate_connector_hostname_for_ssrf(host or "")


class CouchbaseVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Couchbase"
    description = "Couchbase Vector Store with search capabilities"
    name = "Couchbase"
    icon = "Couchbase"

    inputs = [
        SecretStrInput(
            name="couchbase_connection_string", display_name="Couchbase Cluster connection string", required=True
        ),
        StrInput(name="couchbase_username", display_name="Couchbase username", required=True),
        SecretStrInput(name="couchbase_password", display_name="Couchbase password", required=True),
        StrInput(name="bucket_name", display_name="Bucket Name", required=True),
        StrInput(name="scope_name", display_name="Scope Name", required=True),
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        StrInput(name="index_name", display_name="Index Name", required=True),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> CouchbaseVectorStore:
        _validate_couchbase_hosts(self.couchbase_connection_string)
        try:
            from couchbase.auth import PasswordAuthenticator
            from couchbase.cluster import Cluster
            from couchbase.options import ClusterOptions
        except ImportError as e:
            msg = "Failed to import Couchbase dependencies. Install it using `uv pip install langflow[couchbase] --pre`"
            raise ImportError(msg) from e

        try:
            auth = PasswordAuthenticator(self.couchbase_username, self.couchbase_password)
            options = ClusterOptions(auth)
            cluster = Cluster(self.couchbase_connection_string, options)

            cluster.wait_until_ready(timedelta(seconds=5))
        except Exception as e:
            msg = f"Failed to connect to Couchbase: {e}"
            raise ValueError(msg) from e

        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            couchbase_vs = CouchbaseVectorStore.from_documents(
                documents=documents,
                cluster=cluster,
                bucket_name=self.bucket_name,
                scope_name=self.scope_name,
                collection_name=self.collection_name,
                embedding=self.embedding,
                index_name=self.index_name,
            )

        else:
            couchbase_vs = CouchbaseVectorStore(
                cluster=cluster,
                bucket_name=self.bucket_name,
                scope_name=self.scope_name,
                collection_name=self.collection_name,
                embedding=self.embedding,
                index_name=self.index_name,
            )

        return couchbase_vs

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )

            data = docs_to_data(docs)
            self.status = data
            return data
        return []
