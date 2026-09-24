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

check_image_authentication() {
  local image=$1 container_id
  # Retain the image's AUTO_LOGIN default. Never override it in this test.
  container_id=$("$runtime" run -d \
    -e LANGFLOW_SUPERUSER_PASSWORD=ContainerAuthSmoke-2026! \
    -e DO_NOT_TRACK=true \
    -e LANGFLOW_SKIP_MCP_AUTO_INIT=true \
    -e LANGFLOW_MODELS_DEV_REFRESH=false \
    "$image")
  "$runtime" cp scripts/ci/check_authentication.py "$container_id:/tmp/check_authentication.py"
  if ! "$runtime" exec "$container_id" python /tmp/check_authentication.py; then
    echo "Authentication smoke check failed for $image" >&2
    "$runtime" logs "$container_id" || true
    return 1
  fi
  "$runtime" rm -f "$container_id" >/dev/null
}

"$runtime" build -t langflowai/langflow:latest-dev \
  -f docker/build_and_push.Dockerfile .
actual_main_version=$("$runtime" run --rm --entrypoint python langflowai/langflow:latest-dev \
  -c 'from langflow.utils.version import get_version_info; print(get_version_info()["version"])')
[[ "$actual_main_version" == "$main_version" ]] || {
  echo "Expected main version $main_version; got $actual_main_version" >&2
  exit 1
}
check_image_authentication langflowai/langflow:latest-dev

"$runtime" build -t langflowai/langflow-backend:latest-dev \
  --build-arg LANGFLOW_IMAGE=langflowai/langflow:latest-dev \
  -f docker/build_and_push_backend.Dockerfile .
actual_backend_version=$("$runtime" run --rm --entrypoint python langflowai/langflow-backend:latest-dev \
  -c 'from langflow.utils.version import get_version_info; print(get_version_info()["version"])')
[[ "$actual_backend_version" == "$base_version" ]] || {
  echo "Expected backend version $base_version; got $actual_backend_version" >&2
  exit 1
}
check_image_authentication langflowai/langflow-backend:latest-dev

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

check_image_authentication langflowai/langflow:base-latest-dev

# Keep peak disk usage bounded on the 40 GB ARM runner.
cleanup

"$runtime" build -t langflowai/langflow-frontend:latest-dev \
  -f docker/frontend/build_and_push_frontend.Dockerfile .
