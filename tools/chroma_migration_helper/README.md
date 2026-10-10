# One-time Chroma migration helper

This is a separately built and scanned artifact, not an application dependency
or optional extra. Its full hash-locked dependency inventory truthfully includes
Chroma 1.5.9. No dependency override or scanner exclusion hides that fact.

Build from the repository root:

```sh
docker build -f tools/chroma_migration_helper/Dockerfile -t langflow-chroma-migration:qualification .
uv run --no-sync python tools/chroma_migration_helper/qualify.py --image langflow-chroma-migration:qualification
```

The qualification environment needs the Chroma-free application's SQLite
runtime. All source fixture generation occurs in the separate container.
`LANGFLOW_HELPER_TEST_TMPDIR` can select a private parent directory shared with
the local Docker engine. It is a test-harness option, not an application setting.

`export.py` reads a bounded request from stdin and emits protocol-v1 JSONL on
stdout. Its only mounted data is `/source`, read-only. It clones that snapshot
into `/work/source` for native replay. It imports `chromadb_rust_bindings`
directly, disables Python Chroma imports and Python pickle loads, and never
constructs stored embedding functions. A native parser failure omits completion
and returns a sanitized error. The application independently validates the
entire stream before importing anything.

The production launcher requires the dedicated release image by digest and
cosign **v3.1.3**, verified against the expected GitHub Actions signing identity.
The release workflow installs this cosign version by a pinned binary checksum.
The launcher rejects other versions, including versions predating the current
verification fixes. It does not accept the development image tag used above.
Its fixed profile disables
networking and privilege escalation, drops capabilities, uses a non-root user,
mounts the root filesystem read-only and bounds native replay in tmpfs. It also
bounds output and elapsed time and stops the container on cancellation.

## Qualified source matrix

| Source | Qualification |
|---|---|
| Chroma 1.5.9 Rust local HNSW | Supported by the pinned reader and schema validation |
| L2, cosine, inner product | Exact IDs/text/metadata/float32 vectors compared after import |
| Persisted indexes with purged logs | Fixture forces persistence and includes pending operations |
| Deleted IDs, updated rows, empty known-dimension stores | Covered by real native export/import |
| Malformed native index metadata | Must fail without a completion manifest |
| Python SDK embedding definitions / Python pickle execution | Disabled in exporter |
| SPANN or unknown historical formats | Not qualified, fail explicitly |
| Sources larger than 8 GiB or more than 100,000 files | Exceed initial helper limits |
| Remote Chroma/Cloud | Requires a different, operator-coordinated export |

The CI workflow builds and runs the reader on Linux amd64 and arm64, publishes
its SBOM and vulnerability report, and allows signed publication only through
the separate release job and environment. Reports may contain findings. Release
engineering must review the report, record a security disposition, configure
approval protection on the release environment and publish the signed artifact.
The application must not claim this helper is Chroma-free or vulnerability-free.

An offline kit consists of the per-platform image archives, signed
`helper-release.json`, its `helper-verification.sigstore.json` bundle, SBOM and
security disposition. The signed manifest binds the approved multi-platform
registry digest to each qualified image's content ID and archive SHA-256.
Docker save/load can discard repository digests, so the offline launcher uses
the verified **content ID**, never a mutable local image tag.

Before entering the air gap, provision cosign v3.1.3 and obtain Sigstore's
trusted root through cosign's authenticated TUF initialization:

```sh
TUF_ROOT=/private/controller-trust/sigstore cosign initialize
```

Preserve `/private/controller-trust/sigstore/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json`
through the controller's trusted configuration channel. A root file distributed
only inside an untrusted helper kit cannot establish that kit's authenticity.
There is no trust-root download or override inside the application.

In the air gap, verify the release manifest with that trusted root before
loading the archive:

```sh
cosign verify-blob \
  --bundle /private/helper-kit/helper-verification.sigstore.json \
  --trusted-root /private/controller-trust/sigstore/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json \
  --certificate-identity https://github.com/langflow-ai/langflow/.github/workflows/chroma-migration-helper.yml@refs/heads/release-1.13.0 \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  /private/helper-kit/helper-release.json
```

Compare the archive's SHA-256 with the matching platform entry in that verified
manifest, then use `docker load --input <archive>`. Keep these absolute paths
configured until helper cleanup completes:

```sh
LANGFLOW_KB_MIGRATION_HELPER_IMAGE=ghcr.io/langflow-ai/langflow-chroma-migration@sha256:<release digest>
LANGFLOW_KB_MIGRATION_HELPER_BUNDLE=/private/helper-kit/helper-verification.sigstore.json
LANGFLOW_KB_MIGRATION_HELPER_MANIFEST=/private/helper-kit/helper-release.json
LANGFLOW_KB_MIGRATION_HELPER_TRUSTED_ROOT=/private/controller-trust/sigstore/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json
```

The application independently verifies private copies of the manifest and
bundle with `verify-blob --trusted-root` and checks the expected release before
verifying the signed `content_sha256` against the loaded image's complete
execution configuration, platform, and uncompressed filesystem layer hashes.
The archive retains the tag `langflow-chroma-migration-offline:<content_sha256>`.
That tag is used only for inspection. The reader runs by the verified local
immutable ID with `--pull=never`, on either Docker image store. Its offline path
performs neither a registry request nor a package install or image pull. CI
exercises this command with networking disabled and rejects changed content.
The signed release manifest is also verified with networking disabled before
publication. Only the separately protected release job may sign project
artifacts. Synthetic qualification never signs or publishes a release.

Before dispatching a release, a repository administrator must configure the
`chroma-migration-helper-release` environment with at least one required user or
team reviewer. The workflow checks the environment through GitHub's read-only
API with `actions: read` before building a publication candidate and rechecks
before signing and durable publication. An absent or inaccessible environment,
an API error, missing required reviewers, allowed self-review, or enabled
administrator bypass blocks publication. The workflow
does not create or configure the environment. A wait timer alone is insufficient.

See [application upgrade and recovery](../../docs/development/sqlite-kb-upgrade.md)
for the stopped-worker receipt, metadata backup, automatic coordinator and
release qualification boundaries.
