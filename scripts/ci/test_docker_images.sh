#!/usr/bin/env bash

set -euo pipefail

if command -v docker >/dev/null 2>&1; then
  runtime=docker
elif command -v podman >/dev/null 2>&1; then
  runtime=podman
else
  echo "Neither docker nor podman is available." >&2
  exit 1
fi

images=(
  langflowai/langflow:latest-dev
  langflowai/langflow:base-latest-dev
  langflowai/langflow-backend:latest-dev
  langflowai/langflow-frontend:latest-dev
)

cleanup() {
  local image container_id
  for image in "${images[@]}"; do
    while read -r container_id; do
      [[ -z "$container_id" ]] || "$runtime" rm -f "$container_id" >/dev/null 2>&1 || true
    done < <("$runtime" ps -aq --filter "ancestor=$image" 2>/dev/null || true)
    "$runtime" rmi "$image" >/dev/null 2>&1 || true
  done
  "$runtime" system prune -af --volumes >/dev/null 2>&1 || true
  if [[ "$runtime" == docker ]]; then
    docker buildx prune -af >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "Using container runtime: $runtime"
echo "Disk and container storage before cleanup:"
df -h / || true
"$runtime" system df || true
if [[ "$runtime" == docker ]]; then
  docker buildx du || true
fi

cleanup

echo "Disk and container storage after cleanup:"
df -h / || true
"$runtime" system df || true

main_version=$(python3 -c 'import pathlib, tomllib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"])')
base_version=$(python3 -c 'import pathlib, tomllib; print(tomllib.loads(pathlib.Path("src/backend/base/pyproject.toml").read_text())["project"]["version"])')

"$runtime" build -t langflowai/langflow:latest-dev \
  -f docker/build_and_push.Dockerfile .
actual_main_version=$("$runtime" run --rm --entrypoint python langflowai/langflow:latest-dev \
  -c 'from langflow.utils.version import get_version_info; print(get_version_info()["version"])')
[[ "$actual_main_version" == "$main_version" ]] || {
  echo "Expected main version $main_version; got $actual_main_version" >&2
  exit 1
}

"$runtime" build -t langflowai/langflow-backend:latest-dev \
  --build-arg LANGFLOW_IMAGE=langflowai/langflow:latest-dev \
  -f docker/build_and_push_backend.Dockerfile .
actual_backend_version=$("$runtime" run --rm --entrypoint python langflowai/langflow-backend:latest-dev \
  -c 'from langflow.utils.version import get_version_info; print(get_version_info()["version"])')
[[ "$actual_backend_version" == "$base_version" ]] || {
  echo "Expected backend version $base_version; got $actual_backend_version" >&2
  exit 1
}

# The backend build must consume the just-built main image. Once both are
# verified, release their layers before building the standalone base image.
cleanup

"$runtime" build -t langflowai/langflow:base-latest-dev \
  -f docker/build_and_push.Dockerfile --target base .
actual_base_version=$("$runtime" run --rm --entrypoint python langflowai/langflow:base-latest-dev \
  -c 'from importlib.metadata import version; print(version("langflow-base"))')
[[ "$actual_base_version" == "$base_version" ]] || {
  echo "Expected base version $base_version; got $actual_base_version" >&2
  exit 1
}

"$runtime" run --rm --entrypoint python langflowai/langflow:base-latest-dev -c '
import importlib.metadata as metadata
names = {dist.metadata["Name"].lower() for dist in metadata.distributions()}
required = {"langflow-base", "lfx", "langflow-sdk"}
missing = sorted(required - names)
forbidden = sorted(
    name for name in names
    if name.startswith("lfx-") or name in {"langflow-core", "torch", "torchvision"}
)
assert not missing, f"missing base distributions: {missing}"
assert not forbidden, f"extension distributions installed: {forbidden}"
'
"$runtime" run --rm --entrypoint bash langflowai/langflow:base-latest-dev -c \
  'command -v langflow >/dev/null && ! command -v langflow-base >/dev/null'

base_container=$("$runtime" run -d \
  -e LANGFLOW_SUPERUSER_PASSWORD=BaseImageTest-2026! \
  langflowai/langflow:base-latest-dev)
base_healthy=false
for _ in $(seq 1 60); do
  if "$runtime" exec "$base_container" curl -fsS http://127.0.0.1:7860/health_check >/dev/null; then
    base_healthy=true
    break
  fi
  if [[ $("$runtime" inspect -f '{{.State.Running}}' "$base_container" 2>/dev/null) != true ]]; then
    break
  fi
  sleep 2
done
if [[ "$base_healthy" != true ]]; then
  echo "Base image did not become healthy." >&2
  "$runtime" logs "$base_container" || true
  exit 1
fi
"$runtime" rm -f "$base_container" >/dev/null

# Keep peak disk usage bounded on the 40 GB ARM runner.
cleanup

"$runtime" build -t langflowai/langflow-frontend:latest-dev \
  -f docker/frontend/build_and_push_frontend.Dockerfile .
