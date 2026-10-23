#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST_DIR="$ROOT_DIR/deploy/local-kubernetes"
NAMESPACE="langflow"
DEFAULT_IMAGE="docker.io/langflowai/langflow:1.13.0rc4"
IMAGE="${LANGFLOW_IMAGE:-$DEFAULT_IMAGE}"
PRELOAD_CONTEXT=""
PRELOAD_POD=""
FERNET_PATCH_FILE=""

usage() {
  cat <<'EOF'
Usage: scripts/kubernetes/langflow-local.sh <image|up|status|forward|k9s|egress-on|egress-off|fix-fernet-key|down>

Commands:
  image    Preload the pinned image onto the local Kubernetes node.
  up       Create the namespace secret and apply the local Kubernetes manifests.
  status   Show Langflow resources in the namespace.
  forward  Forward localhost:7860 to the Langflow service (foreground).
  k9s      Open k9s in the local context and langflow namespace.
  egress-on  Allow all outbound connections from Langflow.
  egress-off Restore the default deny-egress policy.
  fix-fernet-key Replace the Langflow Fernet key and restart the deployment.
  down     Delete the complete langflow namespace and its namespaced resources.

Set LANGFLOW_K8S_CONTEXT to select a local context and LANGFLOW_IMAGE to override
the image reference. The image command pulls only when the node has no cached copy;
deployment uses imagePullPolicy Never and never pulls from a registry.
EOF
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Required command not found: %s\n' "$1" >&2
    exit 1
  }
}

generate_fernet_key() {
  openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n'
}

cleanup_fernet_patch() {
  if [[ -n "$FERNET_PATCH_FILE" ]]; then
    rm -f "$FERNET_PATCH_FILE"
  fi
}

local_context() {
  require_command kubectl
  local context
  context="${LANGFLOW_K8S_CONTEXT:-$(kubectl config current-context)}"
  case "$context" in
    *local*|colima|k3d|k3d-*|kind|kind-*|minikube)
      printf '%s' "$context"
      ;;
    *)
      printf 'Refusing non-local-looking Kubernetes context: %s\n' "$context" >&2
      printf 'Set LANGFLOW_K8S_CONTEXT to a local context such as k3s-local or colima.\n' >&2
      exit 1
      ;;
  esac
}

wait_for_local_cluster() {
  local context="$1"
  kubectl --context "$context" wait --for=condition=Ready nodes --all --timeout=180s
  if kubectl --context "$context" --namespace cattle-system get service rancher-webhook >/dev/null 2>&1; then
    printf 'Waiting for the Rancher namespace webhook to have a ready endpoint.\n'
    kubectl --context "$context" --namespace cattle-system wait \
      --for=jsonpath='{.subsets[0].addresses[0].ip}' endpoints/rancher-webhook --timeout=180s
  fi
}

create_runtime_secret() {
  local context="$1"
  local password="${LANGFLOW_SUPERUSER_PASSWORD:-}"
  local confirmation=""
  local secret_key
  local secret_file

  if kubectl --context "$context" --namespace "$NAMESPACE" get secret langflow-runtime >/dev/null 2>&1; then
    printf 'Using existing %s/langflow-runtime secret.\n' "$NAMESPACE"
    return
  fi

  require_command openssl
  if [[ -z "$password" ]]; then
    read -r -s -p 'Choose the Langflow superuser password: ' password
    printf '\n' >&2
    read -r -s -p 'Confirm the Langflow superuser password: ' confirmation
    printf '\n' >&2
    if [[ "$password" != "$confirmation" ]]; then
      printf 'Passwords do not match.\n' >&2
      exit 1
    fi
  fi
  if [[ -z "$password" ]]; then
    printf 'A non-empty LANGFLOW_SUPERUSER_PASSWORD is required.\n' >&2
    exit 1
  fi

  secret_key="$(generate_fernet_key)"
  secret_file="$(mktemp "${TMPDIR:-/tmp}/langflow-secret.XXXXXX")"
  trap 'rm -f "$secret_file"' EXIT
  chmod 600 "$secret_file"
  printf 'SUPERUSER_PASSWORD=%s\nSECRET_KEY=%s\n' "$password" "$secret_key" > "$secret_file"
  kubectl --context "$context" --namespace "$NAMESPACE" create secret generic langflow-runtime \
    --from-env-file="$secret_file" --dry-run=client -o yaml |
    kubectl --context "$context" apply -f -
  rm -f "$secret_file"
  trap - EXIT
  unset password confirmation secret_key
}

main() {
  local action="${1:-}"
  local context
  case "$action" in
    image)
      context="$(local_context)"
      wait_for_local_cluster "$context"
      PRELOAD_CONTEXT="$context"
      PRELOAD_POD="langflow-image-preload-$$"
      cleanup_image_pod() {
        kubectl --context "$PRELOAD_CONTEXT" --namespace default delete pod "$PRELOAD_POD" \
          --ignore-not-found=true >/dev/null 2>&1 || true
      }
      trap cleanup_image_pod EXIT
      trap 'exit 130' INT
      trap 'exit 143' TERM
      printf 'Preloading %s through the local Kubernetes node. Registry access is needed only if it is not cached.\n' "$IMAGE"
      kubectl --context "$context" --namespace default run "$PRELOAD_POD" \
        --image="$IMAGE" --image-pull-policy=IfNotPresent --restart=Never \
        --overrides='{"apiVersion":"v1","spec":{"automountServiceAccountToken":false}}' \
        --command -- /bin/sh -c 'exit 0'
      if ! kubectl --context "$context" --namespace default wait \
        --for=jsonpath='{.status.phase}'=Succeeded "pod/$PRELOAD_POD" --timeout=300s; then
        kubectl --context "$context" --namespace default describe pod "$PRELOAD_POD" || true
        return 1
      fi
      cleanup_image_pod
      trap - EXIT INT TERM
      printf 'Image cached on the local Kubernetes node.\n'
      ;;
    up)
      context="$(local_context)"
      kubectl --context "$context" get nodes >/dev/null
      wait_for_local_cluster "$context"
      if ! kubectl --context "$context" get storageclass local-path >/dev/null 2>&1; then
        printf 'StorageClass local-path is required (provided by the standard k3s local-path provisioner).\n' >&2
        exit 1
      fi
      kubectl --context "$context" apply -f "$MANIFEST_DIR/namespace.yaml"
      create_runtime_secret "$context"
      kubectl --context "$context" apply -k "$MANIFEST_DIR"
      if [[ "$IMAGE" != "$DEFAULT_IMAGE" ]]; then
        kubectl --context "$context" --namespace "$NAMESPACE" set image deployment/langflow "langflow=$IMAGE"
      fi
      kubectl --context "$context" --namespace "$NAMESPACE" rollout status deployment/langflow --timeout=180s
      printf '\nLangflow is deployed in namespace %s.\n' "$NAMESPACE"
      printf 'Run `make k8s-local-forward` to access http://127.0.0.1:7860.\n'
      printf 'Run `make k8s-local-k9s` to inspect the namespace.\n'
      ;;
    status)
      context="$(local_context)"
      kubectl --context "$context" --namespace "$NAMESPACE" get deployment,pods,services,pvc,networkpolicy -o wide
      ;;
    forward)
      context="$(local_context)"
      exec kubectl --context "$context" --namespace "$NAMESPACE" port-forward \
        --address 127.0.0.1 service/langflow 7860:7860
      ;;
    k9s)
      context="$(local_context)"
      require_command k9s
      exec k9s --context "$context" --namespace "$NAMESPACE"
      ;;
    egress-on)
      context="$(local_context)"
      kubectl --context "$context" --namespace "$NAMESPACE" get networkpolicy langflow-deny-egress >/dev/null
      kubectl --context "$context" apply -f "$MANIFEST_DIR/egress-allow.yaml"
      printf 'Outbound network access is enabled for Langflow.\n'
      ;;
    egress-off)
      context="$(local_context)"
      kubectl --context "$context" --namespace "$NAMESPACE" delete networkpolicy langflow-allow-egress \
        --ignore-not-found=true
      printf 'The default deny-egress policy is active.\n'
      ;;
    fix-fernet-key)
      context="$(local_context)"
      require_command openssl
      kubectl --context "$context" --namespace "$NAMESPACE" get secret langflow-runtime >/dev/null
      kubectl --context "$context" --namespace "$NAMESPACE" get deployment langflow >/dev/null
      secret_key="$(generate_fernet_key)"
      if [[ "${#secret_key}" -ne 44 ]]; then
        printf 'Failed to generate a valid Fernet key.\n' >&2
        exit 1
      fi
      encoded_key="$(printf '%s' "$secret_key" | base64 | tr -d '\n')"
      FERNET_PATCH_FILE="$(mktemp "${TMPDIR:-/tmp}/langflow-fernet-patch.XXXXXX")"
      chmod 600 "$FERNET_PATCH_FILE"
      trap cleanup_fernet_patch EXIT
      printf '{"data":{"SECRET_KEY":"%s"}}\n' "$encoded_key" > "$FERNET_PATCH_FILE"
      kubectl --context "$context" --namespace "$NAMESPACE" patch secret langflow-runtime \
        --type=merge --patch-file="$FERNET_PATCH_FILE"
      cleanup_fernet_patch
      FERNET_PATCH_FILE=""
      trap - EXIT
      unset secret_key encoded_key
      kubectl --context "$context" --namespace "$NAMESPACE" rollout restart deployment/langflow
      kubectl --context "$context" --namespace "$NAMESPACE" rollout status deployment/langflow --timeout=180s
      printf 'A new Fernet key is active; the admin password was preserved.\n'
      ;;
    down)
      context="$(local_context)"
      printf 'This deletes namespace %s, including Langflow data, PVCs, and secrets.\n' "$NAMESPACE" >&2
      read -r -p 'Type "delete langflow" to continue: ' confirmation
      if [[ "$confirmation" != 'delete langflow' ]]; then
        printf 'Cleanup cancelled.\n'
        return
      fi
      kubectl --context "$context" delete namespace "$NAMESPACE" --ignore-not-found=true --wait=true --timeout=180s
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
