MAX_RETRY_ATTEMPTS = 5
INGESTION_BATCH_SIZE = 200
EXPONENTIAL_BACKOFF_MULTIPLIER = 2
MIN_KB_NAME_LENGTH = 3
CHUNK_PREVIEW_MULTIPLIER = 3

# Safety bounds for user-supplied chunking parameters. The upper
# bounds cap the worst-case memory footprint of a single request.
# With the defaults below a preview-chunks call peaks at
# max_chunks * chunk_size * CHUNK_PREVIEW_MULTIPLIER == 50 * 10_000 * 3
# == 1.5 MB of text — comfortable even for low-memory deployments.
MIN_CHUNK_SIZE = 1
MAX_CHUNK_SIZE = 10_000
MIN_CHUNK_OVERLAP = 0
MAX_CHUNK_OVERLAP = 5_000
MIN_MAX_CHUNKS = 1
MAX_MAX_CHUNKS = 50

# KB deletion retry constants
MAX_DELETE_RETRIES = 5
DELETE_BACKOFF_SECONDS = 0.5

# User-supplied metadata bounds. Vector stores have varying document-size
# limits; these caps keep a single chunk's metadata blob comfortably under
# every backend's per-document ceiling and prevent metadata-only DoS via the
# ingest API.
KB_METADATA_MAX_KEYS = 16
KB_METADATA_MAX_KEY_LENGTH = 32
KB_METADATA_MAX_VALUE_LENGTH = 256
KB_METADATA_MAX_ARRAY_LENGTH = 16
# Reserved keys are written by the ingestion pipeline itself; user-supplied
# metadata that uses any of these would silently overwrite ingestion-internal
# tags and break the chunks browser filters that key off them.
KB_METADATA_RESERVED_KEYS = frozenset(
    {
        "source",
        "file_name",
        "chunk_index",
        "total_chunks",
        "ingested_at",
        "job_id",
        "source_type",
        "source_metadata",
    }
)
