---
name: langflow-local-kubernetes-cleanup
description: "Remove the local Langflow Kubernetes deployment and all resources in its dedicated namespace. Use when asked to clean up, uninstall, or delete the local Langflow k3s/Kubernetes setup."
user-invocable: true
---

# Clean Up Local Langflow Kubernetes

This skill deletes the complete `langflow` namespace. That removes Langflow pods, services, NetworkPolicies, Secrets, PVCs, and stored flow data. It is intentionally destructive and cannot be undone.

Before running cleanup:

1. Confirm the selected kubeconfig context is local (`k3s-local`, `colima`, or another local context), never a shared/production cluster.
2. Tell the user that deleting the namespace also deletes the Langflow database/files and generated secret key.
3. Run the guarded command from the repository root; it requires typing `delete langflow`.

```sh
make k8s-local-clean
```

Do not use `kubectl delete all`, `helm uninstall`, or a broad cluster cleanup. The command targets only the namespace named `langflow`. The local-path provisioner normally removes the backing volume when the PVC is deleted; report any retained PV if the cluster uses a different reclaim policy.
