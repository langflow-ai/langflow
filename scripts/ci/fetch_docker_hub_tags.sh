#!/usr/bin/env bash

set -euo pipefail

repository="${1:-}"
pagination="${2:-}"
if [[ -z "$repository" || ( -n "$pagination" && "$pagination" != "--all-pages" ) ]]; then
  echo "Usage: $0 <docker-hub-repository> [--all-pages]" >&2
  exit 2
fi

response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

headers=(--header 'Accept: application/json')
if [[ "$pagination" == "--all-pages" && ( -n "${DOCKERHUB_USERNAME:-}" || -n "${DOCKERHUB_TOKEN:-}" ) ]]; then
  if [[ -z "${DOCKERHUB_USERNAME:-}" || -z "${DOCKERHUB_TOKEN:-}" ]]; then
    echo "Both DOCKERHUB_USERNAME and DOCKERHUB_TOKEN are required for authenticated tag reads" >&2
    exit 1
  fi
  # Anonymous Docker Hub reads stop after 1,000 tags. Use the existing publishing
  # credentials for full history, passing the secret through stdin rather than argv.
  http_status="$(jq -cn '{identifier: env.DOCKERHUB_USERNAME, secret: env.DOCKERHUB_TOKEN}' | curl \
    --retry 5 \
    --retry-all-errors \
    --connect-timeout 10 \
    --max-time 60 \
    --silent \
    --show-error \
    --header 'Content-Type: application/json' \
    --data-binary @- \
    --output "$response_file" \
    --write-out "%{http_code}" \
    'https://hub.docker.com/v2/auth/token')"
  if [[ "$http_status" != "200" ]]; then
    echo "Docker Hub authentication failed: HTTP ${http_status}" >&2
    exit 1
  fi
  if ! access_token="$(jq -er '.access_token | strings | select(length > 0)' "$response_file")"; then
    echo "Docker Hub returned an invalid access token" >&2
    exit 1
  fi
  headers+=(--header "Authorization: Bearer $access_token")
fi

# Organization access tokens require the namespace-scoped Docker Hub API.
namespace="${repository%%/*}"
repository_name="${repository#*/}"
tag_endpoint="https://hub.docker.com/v2/namespaces/${namespace}/repositories/${repository_name}/tags"
url="${tag_endpoint}?page_size=100"
while [[ -n "$url" ]]; do
  http_status="$({
    curl \
      --retry 5 \
      --retry-all-errors \
      --connect-timeout 10 \
      --max-time 60 \
      --silent \
      --show-error \
      "${headers[@]}" \
      --output "$response_file" \
      --write-out "%{http_code}" \
      "$url"
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
  if [[ "$pagination" != "--all-pages" ]]; then
    break
  fi
  if ! jq -e 'has("next") and (.next == null or ((.next | type) == "string" and (.next | length) > 0))' \
    "$response_file" >/dev/null; then
    echo "Docker Hub returned invalid pagination for ${repository}" >&2
    exit 1
  fi
  url="$(jq -r '.next // empty' "$response_file")"
  if [[ -n "$url" && "$url" != "${tag_endpoint}?"* ]]; then
    echo "Docker Hub returned an unexpected next page for ${repository}" >&2
    exit 1
  fi
done
