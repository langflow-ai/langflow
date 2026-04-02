# Langflow Helm Chart

Deploy a per-employee Langflow instance with SK hynix SSO (Keycloak).

Each `helm install` creates: **Deployment, Service, Ingress, PVC, Secret** — all tied to one employee number.

## Prerequisites

- Kubernetes cluster with an Ingress controller
- `helm` CLI installed
- Wildcard DNS: `*.aipp02.skhynix.com` pointing to your Ingress controller
- Keycloak client with redirect URI: `http://langflow-*.aipp02.skhynix.com/*`

## Quick Start

```bash
helm install langflow-2074795 helm/langflow \
  --set empno=2074795 \
  --set keycloak.serverUrl=https://keycloak.skhynix.com \
  --set keycloak.realm=company \
  --set keycloak.clientId=langflow \
  --set keycloak.clientSecret=your-client-secret \
  --set langflow.secretKey=your-random-32-char-key
```

Access: `http://langflow-2074795.aipp02.skhynix.com`

Only employee `2074795` can log in. Anyone else gets "접근 권한 없습니다".

## With SSL Certificate (Corporate PKI)

If your Keycloak uses an internal CA certificate:

```bash
helm install langflow-2074795 helm/langflow \
  --set empno=2074795 \
  --set keycloak.serverUrl=https://keycloak.skhynix.com \
  --set keycloak.realm=company \
  --set keycloak.clientId=langflow \
  --set keycloak.clientSecret=your-client-secret \
  --set langflow.secretKey=your-random-32-char-key \
  --set ssl.enabled=true \
  --set-file ssl.caCert=./your-ca-cert.pem
```

Or use an existing ConfigMap/Secret that already contains the CA cert:

```bash
# If you already have a ConfigMap with the cert
helm install langflow-2074795 helm/langflow \
  --set empno=2074795 \
  --set keycloak.serverUrl=https://keycloak.skhynix.com \
  --set keycloak.realm=company \
  --set keycloak.clientId=langflow \
  --set keycloak.clientSecret=your-client-secret \
  --set langflow.secretKey=your-random-32-char-key \
  --set ssl.enabled=true \
  --set ssl.existingConfigMap=my-ca-cert-configmap \
  --set ssl.key=ca.crt
```

## Using a values file

For repeated deployments, create a shared values file:

```yaml
# values-production.yaml
keycloak:
  serverUrl: https://keycloak.skhynix.com
  realm: company
  clientId: langflow
  clientSecret: your-client-secret
ssl:
  enabled: true
  existingConfigMap: corporate-ca-cert
  key: ca.crt
langflow:
  secretKey: your-random-32-char-key
```

Then deploy each employee with one line:

```bash
helm install langflow-2074795 helm/langflow -f values-production.yaml --set empno=2074795
helm install langflow-2073215 helm/langflow -f values-production.yaml --set empno=2073215
```

## Manage

```bash
# List all instances
helm list | grep langflow

# Check status
kubectl get pods,svc,ingress -l app.kubernetes.io/name=langflow

# Upgrade (e.g. new image tag)
helm upgrade langflow-2074795 helm/langflow -f values-production.yaml \
  --set empno=2074795 \
  --set image.tag=v1.8.0-hynix-rc3

# Delete
helm uninstall langflow-2074795
```

## Parameters

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `empno` | Employee number | Yes | - |
| `image.repository` | Docker image | No | `dk02315/langflow-hynix` |
| `image.tag` | Image tag | No | `v1.8.0-hynix-rc2` |
| `ingress.enabled` | Create Ingress | No | `true` |
| `ingress.domain` | Base domain | No | `aipp02.skhynix.com` |
| `keycloak.serverUrl` | Keycloak URL | Yes | - |
| `keycloak.realm` | Keycloak realm | Yes | - |
| `keycloak.clientId` | Keycloak client ID | Yes | - |
| `keycloak.clientSecret` | Keycloak client secret | Yes* | - |
| `keycloak.employeeClaim` | Token claim for empno | No | `preferred_username` |
| `ssl.enabled` | Mount CA cert | No | `false` |
| `ssl.caCert` | CA cert PEM content | No | - |
| `ssl.existingConfigMap` | Existing ConfigMap with cert | No | - |
| `ssl.existingSecret` | Existing Secret with cert | No | - |
| `ssl.key` | Key name in ConfigMap/Secret | No | `ca.crt` |
| `langflow.secretKey` | Session signing key | Yes* | - |
| `langflow.storage` | PVC size | No | `5Gi` |
| `resources` | CPU/memory limits | No | - |

*Not required if `keycloak.existingSecret` is set.
