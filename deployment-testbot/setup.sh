#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Building Langflow from source (backend-only, no frontend — still heavy: uv sync + Python deps)..."
docker compose -f docker-compose.yml up -d --build
echo "Waiting for /health_check on :8094 (up to ~15 min for first-run dependency install + DB migrations)..."
for i in $(seq 1 300); do
  if curl -sf -m5 -o /dev/null http://localhost:8094/health_check; then
    echo "Langflow healthy after $((i*3))s"
    break
  fi
  sleep 3
  [ "$i" = 300 ] && { echo "unhealthy after 15 min — dumping logs"; docker compose logs --tail 200; exit 1; }
done
echo "Setup complete"
