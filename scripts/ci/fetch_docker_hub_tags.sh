#!/usr/bin/env bash

set -euo pipefail

repository="${1:-}"
if [[ -z "$repository" ]]; then
  echo "Usage: $0 <docker-hub-repository>" >&2
  exit 2
fi

response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

http_status="$({
  curl \
    --retry 5 \
    --retry-all-errors \
    --connect-timeout 10 \
    --max-time 60 \
    --silent \
    --show-error \
    --output "$response_file" \
    --write-out "%{http_code}" \
    "https://registry.hub.docker.com/v2/repositories/${repository}/tags?page_size=100"
})"

if [[ "$http_status" != "200" ]]; then
  echo "Docker Hub tag lookup failed for ${repository}: HTTP ${http_status}" >&2
  exit 1
fi

if ! jq -e '(.results | type == "array") and all(.results[]; (.name | type) == "string")' \
  "$response_file" >/dev/null; then
  echo "Docker Hub returned an invalid tag response for ${repository}" >&2
  exit 1
fi

jq -r '.results[].name' "$response_file"
