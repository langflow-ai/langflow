# Reusable Docker workflows

The deprecated `docker-build.yml` reusable workflow has been removed. Callers
must use the workflow that matches the publication contract:

- Use `docker-build-v2.yml` for normal releases (`release`, `base`,
  `main`, `main-all`, `ep`, and `nightly-bundle`).
- Use `docker-nightly-build.yml` for nightly base and main image builds. It
  retries a failed architecture once on a fresh runner and publishes manifests
  only after every architecture succeeds.

External callers should pin a commit or tag instead of following a mutable
branch so interface changes can be adopted deliberately.
