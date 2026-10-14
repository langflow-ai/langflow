#!/usr/bin/env bash
# Retry the Docker image test when an export fails but this runner stays up.
# A shutdown signal kills this process; the workflow starts the next attempt
# on a new runner.

set -euo pipefail

limit=()
if command -v timeout >/dev/null 2>&1; then
  limit=(timeout --signal=TERM 30m)
fi

for attempt in 1 2 3; do
  echo "Docker image test attempt ${attempt}/3"
  if "${limit[@]}" bash scripts/ci/test_docker_images.sh; then
    exit 0
  fi
  if [[ "$attempt" -lt 3 ]]; then
    echo "Build failed or the export was interrupted; retrying..."
    sleep 15
  fi
done

exit 1
