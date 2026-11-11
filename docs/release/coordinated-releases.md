# Coordinated OSS releases

This entry point implements the OSS portion of the operator coordinator's
Contract v1. It prepares staging images and immutable component results. The
coordinator owns QA approval and customer publication. Provisioning and live
release acceptance are separate from this repository's fixture tests.

## Workflow boundaries

`coordinated-release.yml` accepts two `workflow_dispatch` inputs:

* `release_request`: JSON envelope `{"request": {...}, "request_digest": "sha256:..."}`.
* `invocation_id`: exactly the request's invocation identifier.

The workflow run name is exactly `invocation_id`, matching the coordinator's
native-run lookup. Configure its OSS `pipeline_id` as `coordinated-release.yml`
and its trusted `workflow_ref` as `main`. The native workflow SHA identifies the
automation, while `request.source.commit` identifies the application source.
They need not be the same. Never find a build by selecting the newest run.

The request contains `schema_version: 1`, `coordinator_id`, `invocation_id`,
`component: "oss"`, `version`, `mode`, `candidate`, `release_id`, `source`,
`oss_commit`, `platforms`, `dependencies: {}`, and `destination`. Source repository
is `https://github.com/langflow-ai/langflow`; source branch is `release-X.Y.Z`;
source commit is a full lowercase SHA and equals `oss_commit`. The request digest
uses SHA-256 over sorted, compact, UTF-8 JSON with `ensure_ascii=False`, including
the request only. Do not add a digest field inside the hashed request.

| Mode | Candidate | Image/UI version | Python application version |
| --- | --- | --- | --- |
| RC | `rc.1` | `1.14.0-rc.1` | `1.14.0rc1` |
| Official | null | `1.14.0` | `1.14.0` |

Official mode receives the approved source from the coordinator. It does not
resolve a release branch again. Packaging changes are made in a disposable
context; they are not commits on the release branch. Independently versioned
SDK, executor and provider packages retain their own versions.

The existing `docker-build-v2.yml` workflow remains the standalone interface for
selected branches or commits, with `ref`, `version_override`, `pre_release`, and
`push_to_registry`. Existing package release, nightly and compliance paths are
unchanged. The coordinated workflow wraps the source Docker build separately
because the existing workflow also manages normal publication destinations and
aliases. A standalone build is not a QA-approved coordinated release.

## Result transfer to the coordinator

Successful builds upload a single `component-result.json` using an immutable
GitHub Actions artifact named
`release-result-<invocation_id>`, retrieved only through its exact native run's
artifact listing. The upload requests 90 days of retention, and the workflow
rejects a shorter effective `GITHUB_RETENTION_DAYS` before reserving or building
an image. Provision the repository/organization retention policy accordingly.
Transfer immediately after native success; the protected durable store must
retain the accepted result through QA, official release and recovery. GitHub's
public-repository limit is 90 days, so GitHub alone cannot provide indefinite
recovery. See the [retention policy](https://docs.github.com/en/organizations/managing-organization-settings/configuring-the-retention-period-for-github-actions-artifacts-and-logs-in-your-organization).
A native failure, cancellation,
missing artifact, repeated attempt, duplicate correlation, or mismatched result
does not satisfy a coordinator dependency. Rerunning a GitHub run is deliberately
unsupported: Contract v1 has no native attempt field. Use the coordinator's
explicit retry/reconciliation process.

The result records the canonical request digest, invocation/component/release
identity, source and OSS SHAs, native handle, registry index digest and platform
manifest digests, `publication: "staged"`, and packaging/smoke evidence. Every
platform config must carry `org.opencontainers.image.revision`,
`org.opencontainers.image.version`, and `langflow.org/release-request` matching
the frozen source, release identity and request digest.

The workflow pulls each verified platform manifest by digest and checks both
installed application package versions, the bundled frontend version marker,
and `langflow --help`. This smoke check does not exercise server startup or
HTTP health; those remain part of live release acceptance.

The operator's current COS deployment service already pulls this exact artifact
name using `release.github_artifacts.fetch_result` and persists it through its
immutable COS store. Configure `store.type: "cos"` and use the built-in `result`
service (remove the POSIX template's explicit `bridges.result` override). Do not
install the POSIX adapter below for that route. Configure an Actions-read GitHub App identity
for the artifact reader, distinct from the Actions-write dispatch identity if
separate identities are required by the deployment policy. The public build
worker needs no private evidence-store or SPS credentials.

Integration handoff: the tested operator runtime's
`release.github_artifacts.fetch_result(payload, execute, settings)` calls
`github_runs.verify_execution` for the trusted workflow/ref, invocation title,
native attempt and successful completion, then verifies the ZIP checksum and
Contract result. `DeploymentServices.call("result")` reads validated COS data
first and fetches GitHub only on confirmed absence. `find_result` exposes that
absence-aware lookup separately. Install the entire pinned runtime containing
these changes together; older readers that lack these checks or always refetch
GitHub do not satisfy the handoff. The validation probe records the exact tested
operator hashes, negative cases and recovery behavior. Live service identity,
COS ACL and retention validation remain deployment prerequisites.

For the original POSIX store deployment, install a reviewed, pinned copy of
`scripts/ci/coordinated_release` on the coordinator worker. It is self-contained
within this repository; no developer worktree is a runtime dependency.
The supplied `coordinated_release.transport` is an alternative multiplexing `result` bridge.
For OSS it first validates the request/native handle and asks the protected
store for an already accepted result. A valid saved result is returned without
GitHub access. Only JSON `null`, meaning confirmed absence, permits ingress; that
path checks the exact native run, trusted workflow/ref, success state, invocation
name, unique artifact, ZIP SHA-256 and complete result before immutable save and
readback. Store failures or malformed saved data never trigger a refetch or
overwrite. Other components pass through to the existing store reader. Configure the `result`
bridge as an argument array equivalent to:

```text
python -m coordinated_release.transport
  --workflow-ref main
  --store-read '["/opt/coordinator/bin/result-store","read"]'
  --store-save '["/opt/coordinator/bin/result-store","save"]'
```

Set `PYTHONPATH` to the pinned checkout's `scripts/ci` directory. The example
`result-store` executable is an absence-aware deployment wrapper around the
coordinator's `release.artifacts` or `CosArtifacts` operations. It must run from
its own separately installed, pinned coordinator environment. Pass JSON on stdin,
return only JSON on stdout, and preserve the existing immutable-write semantics.
Retain the operator's existing `save_result` bridge for its native builds.

The wrapper contract is concrete and does not change Contract v1:

| Operation | Input | Successful output | Failure behavior |
| --- | --- | --- | --- |
| `read` | `{request, request_digest, run}` | Validated result, or JSON `null` only for confirmed missing result | Nonzero for authentication, permission, transport, parse or validation errors |
| `save` | `{request, run, result}` | JSON `true` after immutable save | Nonzero for conflicting bytes or any storage error |

The POSIX `release.artifacts.read` raises `FileNotFoundError` for a missing
result; it cannot be used directly for the initial lookup. A POSIX wrapper may
translate only that exact result-file absence to `null`, after validating the
request/run and verifying the protected mount is present and readable. An absent
mount or permission failure is not an absent result. For COS, the pinned
operator's `find_result` service calls `CosArtifacts.read(payload, missing_ok=True)`;
only a confirmed HTTP 404 yields `null`, while existing bytes receive full
validation. `CosClient` distinguishes 404 from 403, transport failure and invalid
responses. Do not catch all `ContractError` exceptions as absence. Do not route
the transport's store read back through `result`, which would re-enter GitHub
ingress. These wrappers run only on the coordinator worker.

If the separate OSS transport is selected instead of built-in COS ingress, its
store commands can use the operator's existing installed service directly:

```text
--store-read '["/opt/coordinator/runtime/REVIEWED_REVISION/.sps/release/service.sh","--config","/run/release/deployment.json","find_result"]'
--store-save '["/opt/coordinator/runtime/REVIEWED_REVISION/.sps/release/service.sh","--config","/run/release/deployment.json","save_result"]'
```

Replace `REVIEWED_REVISION` with the deployed immutable runtime revision and use
the protected deployment configuration. The built-in COS route needs no result
bridge override; this alternative is for deployments choosing the OSS verifier.

Transfer promptly while the GitHub artifact is retained. Persistence is keyed
by the canonical native-handle hash in the coordinator store; a second save must
match the existing bytes. A transfer failure can retry reading the same native
artifact without rebuilding or republishing the image. Do not redispatch after
an uncertain acknowledgement. Once persistence succeeded, retries read that
validated immutable result even if GitHub is unavailable or the artifact expired.

The API behavior used here is documented in GitHub's [artifact API](https://docs.github.com/en/rest/actions/artifacts)
and [workflow run API](https://docs.github.com/en/rest/actions/workflow-runs).

## Branch lifecycle

The separate `create-next-release-branches.yml` handles completed same-repository
`release-X.Y.Z` merges into `main`. It re-fetches the exact PR and matches its
identity and source/merge SHAs to the event. It never checks out or runs PR code.

| Completed merge | Created patch source | Additional minor source |
| --- | --- | --- |
| `release-1.14.0` | `release-1.14.1` at final release head | `release-1.15.0` at resulting main merge |
| `release-1.14.1` | `release-1.14.2` at final release head | None |
| `release-1.14.2` | `release-1.14.3` at final release head | None |

Existing exact or descendant branches are preserved. Unexpected ancestry is
reported and never reset, including concurrent creation. Branch creation does
not publish images, Python packages, tags or GitHub releases. Release-to-main and
main-to-next-minor merges remain manual.

## Ownership and rollout handoff

This change adds new workflows, release helpers, tests and this runbook. It does
not edit the normal Dockerfile, normal release workflows, the shared coordinator
contract, shared infrastructure configuration, forward-port/label enforcement,
required checks, protection policies or rulesets. The policy owner must provision
and verify release-branch coverage before branch automation is enabled.

The coordinator/infrastructure owner supplies the dedicated staging repository,
immutable-tag policy, atomic image reservation service, scoped service identities,
approved platform policy, protected workflow environment and worker configuration,
and durable result-store mount. Customer repositories and entitlement checks stay
with the coordinator. Main/standalone identities must not receive coordinated
staging reservation or customer-publication authority.

Provision the following before enabling either workflow:

| Location | Setting | Required value or responsibility |
| --- | --- | --- |
| GitHub environment | `coordinated-release-staging` | Restrict to trusted `main`; review who can dispatch and access staging secrets. |
| Repository/organization setting | Actions artifact/log retention | 90 days; the workflow checks `GITHUB_RETENTION_DAYS` before staging reservation. Durable-store retention must cover the full QA/release/recovery lifetime. |
| Repository variable | `COORDINATED_RELEASE_ENABLED` | `true` only after the protected worker and staging integrations are ready. |
| Repository/environment variable | `COORDINATED_RELEASE_RUNNER` | JSON runner labels, default `["self-hosted","linux","coordinated-release"]`; dedicated ephemeral workers with Docker/Buildx, pinned `crane`, and the protected reservation adapter. |
| Repository/environment variable | `COORDINATED_RESERVATION_ENABLED` | `true` only after atomic reservation and immutable-tag policy are deployed. |
| Repository/environment variable | `COORDINATED_STAGING_REPOSITORIES` | Comma-separated exact staging image repositories; no customer repositories. |
| Repository/environment variable | `COORDINATED_RESERVE_IMAGE` | Exact protected JSON argv `["/opt/langflow-release-REVIEWED_COMMIT/.sps/release/reserve-oss.sh","--config","/etc/langflow-release/oss-reservation-client.json"]`; it runs from the separately installed pinned operator runtime, receives `{request, run}` on stdin and returns JSON `true` only after an atomic unique reservation and registry absence check. |
| Repository/environment variable | `COORDINATED_STAGING_REGISTRY` | Registry host matching the allowed staging repository. |
| Environment secrets | `COORDINATED_STAGING_USERNAME`, `COORDINATED_STAGING_TOKEN` | Scoped staging push/read identity with no customer or alias write access. |
| Coordinator configuration | OSS workflow and destination | `pipeline_id: coordinated-release.yml`, `workflow_ref: main`, matching staging repository, and explicitly approved platforms. |
| Coordinator identity | GitHub access | Actions write for dispatch/cancel; Actions read for exact-run polling/artifacts; contents read for source resolution. |
| Repository variable | `RELEASE_BRANCH_AUTOMATION_ENABLED` | `true` only after the policy owner deploys and tests the protection verifier. |
| Repository variable | `RELEASE_BRANCH_AUTOMATION_RUNNER` | Runner capable of executing the preinstalled protection adapter. |
| Repository variable | `RELEASE_PROTECTION_BRIDGE` | JSON argv array; stdin `{repository, branch}`, stdout `{"verified":true}`. Verify approved wildcard coverage before creation and protections after creation. |

The reservation adapter is an infrastructure input, not a repository shell
snippet or a success stub. It must share the coordinator's durable release
ownership, bind the exact request/native run, distinguish registry authorization
errors from a missing tag, and reject duplicate/ambiguous writes. Failed attempts
require the coordinator's no-publication proof before the reservation can be
transferred to a new attempt. An already published identity is never reset.

The operator's concrete `Reservations` implementation writes COS and therefore
must run behind the protected coordinator-side OIDC gateway. The public OSS
worker invokes only the separately installed, pinned runtime launcher above;
it never receives IBM COS or SPS credentials. Provision the client JSON with
deployment-selected values, including a full HTTPS endpoint whose path is
`/v1/reserve/oss` and the matching OIDC audience:

```json
{
  "endpoint": "https://<deployment-selected-reservation-gateway>/v1/reserve/oss",
  "audience": "<deployment-selected-oidc-audience>"
}
```

Only `jobs.build` grants `id-token: write`, allowing GitHub to supply the Actions
OIDC request variables used by this client. The job retains `contents: read`;
the protected ref, environment and release enablement checks still apply.

The protected gateway must bind the exact GitHub subject for the existing
environment, `repo:langflow-ai/langflow:environment:coordinated-release-staging`,
immutable GitHub `repository_id` and `repository_owner_id`, `workflow_ref: main`,
and the approved `workflow_commit`. The audience, endpoint, IDs and reviewed
commit are deployment inputs and must be selected and provisioned by the
infrastructure owner; this repository does not invent them. The OIDC exchange
independently verifies the native run, first attempt and `{request, run}`
payload before the existing conditional reservation returns JSON `true`.

The November 11 SPS `branch`, native `commit-id`, `release-request`, scan/sign
`save_artifact`, and publication-disable properties apply to the IBM component
pipelines. OSS uses the GitHub `workflow_dispatch` envelope and the separate
exact-SHA checkout shown above. The pinned reservation client runs as an external
command. No SPS property or developer-checkout import is added to this public
worker, and no normal OSS release workflow is replaced.

The new workflow assumes ephemeral workers so source builds cannot leave
credentials or executable state for later jobs. Provision supported CPU execution
or QEMU/binfmt for every requested platform; availability of a base-image CPU
descriptor alone is not approval for that platform.

No schema amendment is required. Native GitHub reruns are rejected because the
current native handle omits `run_attempt`; supporting them later requires a shared
contract decision. Artifact transfer is a supplied bridge implementation, not a
new result schema.

Before enabling production use, retain a real RC build, exact-run transfer into
the coordinator, index/platform/config verification, runtime smoke on every
approved platform, a duplicate/retry exercise, and an approved-source official
staging build after a release branch advances. The coordinator's connected and
disconnected installation/upgrade matrix and customer pulls remain required.
Exercise actual `.0`, `.1` and `.2` merge events with the approved protections.
Local tests cannot establish any of those live outcomes.

## Local validation

Run only isolated fixtures; never source the shared SPS credential bootstrap:

```bash
uv run --no-project --python 3.13 --with pytest --with pyyaml --with packaging \
  python -m pytest -o addopts='' scripts/ci/test_coordinated_*.py
```

The new `coordinated-release-tests.yml` runs the focused suite on relevant PRs.
The existing CI scripts suite also discovers these tests. No test changes SSH
files, personal credentials, global Git settings or a live release identity.

For a separately available operator checkout, the optional integration probe
loads its actual `PipelineClient`, GitHub artifact reader, `DeploymentServices`,
`CosClient`, and `CosArtifacts`. Only external commands and HTTP are replaced
with bounded fixtures; unexpected I/O is rejected. It exercises RC/official
canonical identity, dispatch inputs, exact artifact retrieval, conditional COS
writes, immutable conflicts, and malformed or mismatched input rejection:

```bash
uv run --no-project --python 3.13 python scripts/ci/probe_coordinated_operator.py \
  --operator-root /path/to/reviewed-operator-checkout \
  --output /tmp/oss-operator-probe.json
```

The JSON separates supported cases, expected rejections and observed operator
gaps. It records the operator base and source hashes and rejects a source change
during the probe. A completed probe with known gaps is not deployment acceptance.
This is developer validation tooling only: deployed OSS helpers never import
another checkout. Install every runtime adapter separately from reviewed,
pinned sources; a developer worktree path is not a deployment dependency.

The November 11 local review uses OSS base
`2cf9ce808afa6ad3f41aa5f6b47bdcb1927cde84`. Disposable RC and official package
checks use frozen release source
`8178944e20614afe4154d4edc30f9f9f9ed9973c`, with Python 3.13 and offline lock
validation. These metadata checks preserve all non-application package records;
they do not establish image execution. The accompanying local validation receipt
binds the uncommitted OSS file hashes, operator probe snapshot, actual check
commands and remaining enablement blockers. Normal OSS release files remain
unchanged against that base.
