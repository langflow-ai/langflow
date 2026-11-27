---
name: langflow-local-kubernetes
description: "Deploy, inspect, or access Langflow on a local Kubernetes or k3s cluster from this repository. Use for the local Colima/k3s setup, offline image preloading, port forwarding, or opening the Langflow namespace in k9s."
user-invocable: true
---

# Langflow Local Kubernetes

Use this skill for the repository's local, single-instance Kubernetes deployment. Run commands from the repository root. The setup uses the `langflow` namespace, SQLite on a local-path PVC, a ClusterIP service, a local-only port-forward, and an egress-deny NetworkPolicy.

## Prerequisites

- macOS, Colima with its Kubernetes/k3s integration, `kubectl`, `k9s`, and OpenSSL.
- A local Kubernetes context such as `k3s-local` or `colima`; never target a shared or production cluster.
- The `local-path` StorageClass.
- A local Kubernetes node with enough resources for Langflow and the pinned image cached on that node. Registry access is needed only to prefetch a missing image; subsequent deployment is offline-capable.

Recommended Colima initialization for a new local cluster:

```sh
colima start --kubernetes --cpu 4 --memory 8 --disk 60
```

Colima's runtime cannot be changed after a profile is initialized. The workflow works with Colima's existing Docker+k3s runtime; do not delete or recreate an existing profile to change it. Do not start, delete, or reconfigure an existing Colima cluster without an explicit request.

## Quick Start

Run one command to preload the image if needed, deploy Langflow, and open the local port-forward:

```sh
make k8s-local
```

The port-forward stays in the foreground. Open `http://127.0.0.1:7860`; press Ctrl+C to stop forwarding. The deployment remains running. On first deployment, enter the superuser password when prompted. The image is cached on the node, so later starts work offline. For a non-default local context, set `LANGFLOW_K8S_CONTEXT`. To use a custom image, set `LANGFLOW_IMAGE` for the command. Deployment uses `imagePullPolicy: Never` and does not fetch charts or images.

## Optional Commands

```sh
make k8s-local-status       # Show deployment health.
make k8s-local-k9s          # Open the namespace in k9s.
make k8s-local-egress-on    # Allow outbound traffic for external providers.
make k8s-local-egress-off   # Restore network isolation.
```

Egress is denied by default, including DNS. `egress-on` allows all outbound traffic, not only the configured provider; turn it off when finished. Use `/langflow-local-kubernetes-cleanup` to remove the namespace and its data.

## Fresh Reinstall

To erase the existing deployment and start over:

```sh
make k8s-local-clean
make k8s-local
```

Cleanup requires typing `delete langflow` and permanently removes flows, files, credentials, the database, and the admin secret. The next start creates a new admin password and a valid Fernet key. Re-enter provider credentials after reinstalling.

The generated `LANGFLOW_SECRET_KEY` is URL-safe Base64 encoding of 32 random bytes. `make k8s-local-fix-fernet-key` is only for an existing deployment whose key is invalid when you need to preserve its data; a clean reinstall does not need it. Rotation can invalidate credentials encrypted with the old key. Do not expose a NodePort/Ingress unless explicitly requested.

For teardown, use the separate `/langflow-local-kubernetes-cleanup` skill. Namespace deletion removes all data and credentials.
