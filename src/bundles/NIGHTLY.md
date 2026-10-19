# Canonical nightly releases

Nightlies use the canonical package names with coordinated `.devN` versions.
They do not publish parallel `*-nightly` Python distributions.

## Version chain

The workflow derives one coordinated Langflow development version from the
canonical histories of `langflow`, `langflow-base`, `lfx`, and
`langflow-sdk`.

The dependency chain is exact for a nightly:

```text
langflow==X.Y.Z.devN
  -> langflow-base==X.Y.Z.devN
      -> lfx==X.Y.Z.devN
```

The SDK uses the same coordinated version. Standalone extension distributions
retain their canonical names and their bounded LFX compatibility ranges.
If a bundle requires the final LFX release for the line being built, the nightly
tag gives that bundle a `.devN` version and an exact LFX nightly pin. For the same
release, an older RC sorts after every dev version, so a lower bound would still
admit incompatible RCs. The bundle manifest and the full package's dependency floor change together. Compatible
bundles remain unchanged, and the stable source keeps its final-release floor.
Affected extension wheels are built and published before `langflow-base`.

## Publish order

The release workflow publishes in dependency order:

1. `langflow-sdk`
2. `lfx`
3. affected `lfx-*` extension distributions
4. `langflow-base`
5. `langflow`

The `langflow-base` and `langflow` versions must match. A base-only or
full-only nightly version is not supported.

## Installing a nightly

Use prerelease resolution with the canonical package name:

```bash
uv pip install --pre langflow
```

For the runnable application without provider extensions:

```bash
uv pip install --pre langflow-base
```

Both packages provide the `langflow` command.

## Dry runs

The release workflow retains its `dry_run` input. A dry run may use a release
tag, immutable commit SHA, or pull-request ref. It builds and validates every
selected wheel and image, but disables PyPI publication, registry publication,
tag creation, and GitHub Release writes.

## Verification

- Confirm the root and base versions match before building.
- Inspect wheel metadata for exact nightly pins through the SDK/LFX/base/full
  dependency chain.
- Install the local wheels together and run `pip check`.
- Confirm base contains no provider `lfx-*`, PyTorch, or TorchVision
  distributions.
- Confirm full discovers the curated extensions.
- Run `scripts/ci/test_pypi_nightly_tag.py` and the release workflow contract
  tests before enabling publication.
