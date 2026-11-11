# Local Kubernetes Deployment

This setup runs the Langflow IDE as one pod in the `langflow` namespace. It uses SQLite on a local-path PVC, a ClusterIP service, and `kubectl port-forward`; it creates no Ingress or NodePort. The pod has an egress-deny NetworkPolicy and the image uses `imagePullPolicy: Never`, so a fresh deployment does not contact a container registry.

## Prerequisites

- macOS with [Colima](https://github.com/abiosoft/colima), `kubectl`, `k9s`, and OpenSSL installed.
- A local Kubernetes cluster. Colima's lightweight k3s integration is the recommended option; see [Set up Colima](#set-up-colima).
- The active kubeconfig context must look local (`k3s-local`, `colima`, `k3d-*`, `kind-*`, or `minikube`). Set `LANGFLOW_K8S_CONTEXT` to a local context name if you have more than one.
- A `local-path` StorageClass. The standard k3s local-path provisioner provides it.
- The Langflow image cached on the local Kubernetes node. Run `make k8s-local-image` while registry access is available. It creates a temporary pod so Kubernetes pulls the image into the node's own runtime cache; this also works with Colima's Docker+k3s profile. For a fully offline setup, preload/cache the image before disconnecting.

The setup does not install Colima, start or stop a cluster, change the current kubeconfig context, install Helm charts, or contact a registry during deployment. It does not deploy PostgreSQL; the single replica uses SQLite.
Before deployment, the helper waits for the local node and, when present, the Rancher namespace webhook to become ready. This avoids applying the namespace while a local cluster is still starting.

## Set up Colima

Install the local tools with Homebrew if they are not already available:

```sh
brew install colima kubectl k9s
```

Start Colima with Kubernetes enabled. The first start may download the VM and Kubernetes images, so do this while internet access is available:

```sh
colima start --kubernetes --cpu 4 --memory 8 --disk 60
```

Colima fixes the runtime when a profile is first created. A later `--runtime containerd` option cannot change an existing Docker profile and is discarded; this deployment does not require changing the runtime. Do not delete or recreate an existing Colima profile just to change its settings, as that can remove local data. Check the current state first:

```sh
colima status
kubectl config get-contexts
kubectl config current-context
```

If Colima's context is not selected, select the local context shown by `kubectl config get-contexts` (commonly `colima`):

```sh
kubectl config use-context colima
kubectl get nodes
kubectl get storageclass
```

Confirm that a node is `Ready` and that `local-path` is listed before deploying. The Make targets use the current context by default; if needed, select the local context explicitly with `LANGFLOW_K8S_CONTEXT`:

```sh
LANGFLOW_K8S_CONTEXT=colima make k8s-local-status
LANGFLOW_K8S_CONTEXT=colima make k8s-local-k9s
```

The deployment script rejects context names that do not look local. Do not point it at a shared or production cluster. `k9s` and `kubectl` use the same kubeconfig context; no separate k9s cluster setup is needed.

## Deploy and access

```sh
make k8s-local
```

This preloads the image if needed, deploys Langflow, and starts a foreground port-forward to `127.0.0.1:7860`. Open <http://127.0.0.1:7860>; press Ctrl+C to stop forwarding without stopping the deployment. On first deployment, the command prompts for the superuser password and stores it with a generated Fernet key in a Kubernetes Secret. Later runs reuse that Secret. Keep the password safe; cleanup deletes the Secret.

If an earlier setup generated an invalid Fernet key, run `make k8s-local-fix-fernet-key`. It replaces only the encryption key, preserves the admin password, and restarts Langflow. Rotating this key can make credentials encrypted with a previous valid key unreadable.

For status or the k9s view, use `make k8s-local-status` or `make k8s-local-k9s`. To start only the port-forward after the deployment is already running, use `make k8s-local-forward`.

### Start over

To remove the entire deployment and create a fresh one:

```sh
make k8s-local-clean
make k8s-local
```

The cleanup command requires typing `delete langflow`. It permanently removes the namespace, including flows, files, database, provider credentials, and the admin secret. The next start prompts for a new admin password and generates a valid Fernet key; add provider credentials again afterward. You do not need `make k8s-local-fix-fernet-key` for a clean reinstall. Use it only to repair an invalid key while retaining the existing data.

To use a different, already-preloaded image:

```sh
LANGFLOW_IMAGE=registry.local/langflow:tag make k8s-local
```

For a non-Colima cluster, preload the image into every eligible node's container runtime yourself. The deployment uses `imagePullPolicy: Never` intentionally.

## Network access

By default, the NetworkPolicy denies all pod egress, including DNS. This prevents Langflow from reaching public services and model providers. A provider hostname that fails DNS resolution is expected in this mode.

Enable outbound access when you need a provider, then restore isolation when finished:

```sh
make k8s-local-egress-on
# Use Langflow and test the provider.
make k8s-local-egress-off
```

The opt-in policy allows all outbound connections from Langflow, including DNS, public internet, and other reachable network destinations. This lowers isolation and lets flows or custom integrations make arbitrary outbound connections. Keep it off for offline use. NetworkPolicy enforcement depends on the cluster's CNI; k3s's default network policy controller supports it.

Kubernetes manifests and deployment commands are local. Updates to Langflow, image preloading, and any dependencies not bundled in the image must be prepared before the cluster loses registry/network access.

## Inspect and remove

```sh
make k8s-local-status
make k8s-local-k9s
make k8s-local-clean
```

Cleanup requires typing `delete langflow` and removes the entire namespace, including the deployment, secret, PVC, and application data. The local-path provisioner normally deletes the backing volume with the PVC; verify your cluster's reclaim policy if it uses a different storage provisioner.
