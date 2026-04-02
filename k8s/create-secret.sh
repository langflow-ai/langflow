#!/bin/bash
# Create the shared Keycloak secret (run once per namespace)
#
# Usage:
#   bash k8s/create-secret.sh <client-secret> <langflow-secret-key>

set -euo pipefail

CLIENT_SECRET="${1:?Usage: $0 <keycloak-client-secret> <langflow-secret-key>}"
LANGFLOW_SECRET="${2:?Usage: $0 <keycloak-client-secret> <langflow-secret-key>}"

kubectl create secret generic langflow-keycloak-secret \
  --from-literal=client-secret="$CLIENT_SECRET" \
  --from-literal=langflow-secret-key="$LANGFLOW_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secret langflow-keycloak-secret created/updated."
