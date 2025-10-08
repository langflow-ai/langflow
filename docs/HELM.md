# AI Studio Helm Chart Guide

This document provides comprehensive instructions for deploying AI Studio using the unified Helm chart.

## 📁 Chart Structure

```
helmcharts/ai-studio/
├── Chart.yaml                     # Chart metadata
├── values.yaml                    # Default configuration values
└── templates/
    ├── _helpers.tpl                # Template helpers and functions
    ├── frontend-deployment.yaml    # Frontend deployment
    ├── frontend-service.yaml       # Frontend service
    ├── frontend-hpa.yaml          # Frontend horizontal pod autoscaler
    ├── backend-deployment.yaml     # Backend deployment
    ├── backend-service.yaml        # Backend service
    ├── backend-hpa.yaml           # Backend horizontal pod autoscaler
    ├── backend-pvc.yaml           # Backend persistent volume claim
    ├── serviceaccount.yaml        # Service accounts
    ├── ingress.yaml               # Ingress configuration
    ├── NOTES.txt                  # Post-installation notes
    └── tests/
        └── test-connection.yaml    # Helm test resources
```

## 🚀 Quick Start

### Prerequisites

- **Kubernetes cluster**: Version 1.20+
- **Helm**: Version 3.8+
- **kubectl**: Configured to access your cluster
- **Container registry access**: aistudioregistry.azurecr.io

### Basic Installation

```bash
# Add Azure Container Registry credentials (if needed)
kubectl create secret docker-registry acr-secret \
  --docker-server=aistudioregistry.azurecr.io \
  --docker-username=<username> \
  --docker-password=<password>

# Install AI Studio with default values
helm install ai-studio helmcharts/ai-studio/

# Install with custom namespace
helm install ai-studio helmcharts/ai-studio/ -n ai-studio --create-namespace
```

### Custom Installation

```bash
# Install with custom values file
helm install ai-studio helmcharts/ai-studio/ -f custom-values.yaml

# Install with inline value overrides
helm install ai-studio helmcharts/ai-studio/ \
  --set frontend.replicaCount=2 \
  --set backend.resources.limits.memory=16Gi \
  --set global.imageRegistry=myregistry.azurecr.io
```

## ⚙️ Configuration

### Global Configuration

```yaml
global:
  # Image registry for both services
  imageRegistry: "aistudioregistry.azurecr.io"

  # Common labels applied to all resources
  commonLabels:
    environment: "production"
    team: "ai-studio"

  # Service account configuration
  serviceAccount:
    create: true
    name: "ai-studio-sa"
    annotations:
      azure.workload.identity/client-id: "your-client-id"
```

### Frontend Configuration

```yaml
frontend:
  enabled: true
  replicaCount: 2

  image:
    repository: "ai-studio-frontend"
    tag: "v1.0.0"
    pullPolicy: IfNotPresent

  service:
    type: ClusterIP
    port: 3000

  resources:
    limits:
      cpu: 1
      memory: 1Gi
    requests:
      cpu: 500m
      memory: 800Mi

  # Environment variables
  env:
    NODE_ENV: "production"
    VITE_BACKEND_URL: "https://api.ai-studio.com"

  # Auto-scaling configuration
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 5
    targetCPUUtilizationPercentage: 80
```

### Backend Configuration

```yaml
backend:
  enabled: true
  replicaCount: 3

  image:
    repository: "ai-studio-backend"
    tag: "v1.0.0"
    pullPolicy: IfNotPresent

  service:
    type: ClusterIP
    port: 7860

  resources:
    limits:
      cpu: 2
      memory: 8Gi
    requests:
      cpu: 1
      memory: 4Gi

  # Persistent storage for backend data
  persistence:
    enabled: true
    size: 20Gi
    accessMode: ReadWriteOnce
    storageClass: "premium-ssd"

  # Environment variables
  env:
    HOST: "0.0.0.0"
    PORT: "7860"
    LANGFLOW_LOG_LEVEL: "INFO"
    API_PREFIX: "/api/v1"

  # Secret environment variables
  secretEnv:
    LANGFLOW_DATABASE_URL:
      secret: "ai-studio-secrets"
      key: "database-url"

  # Auto-scaling configuration
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 80
    targetMemoryUtilizationPercentage: 80
```

## 🌐 Ingress Configuration

### Basic Ingress

```yaml
frontend:
  ingress:
    enabled: true
    className: "nginx"
    annotations:
      cert-manager.io/cluster-issuer: "letsencrypt-prod"
      nginx.ingress.kubernetes.io/ssl-redirect: "true"
    hosts:
      - host: ai-studio.company.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: ai-studio-tls
        hosts:
          - ai-studio.company.com

backend:
  ingress:
    enabled: true
    className: "nginx"
    annotations:
      cert-manager.io/cluster-issuer: "letsencrypt-prod"
      nginx.ingress.kubernetes.io/ssl-redirect: "true"
    hosts:
      - host: api.ai-studio.company.com
        paths:
          - path: /api
            pathType: Prefix
    tls:
      - secretName: ai-studio-api-tls
        hosts:
          - api.ai-studio.company.com
```

### Advanced Ingress with Rate Limiting

```yaml
frontend:
  ingress:
    annotations:
      nginx.ingress.kubernetes.io/rate-limit: "100"
      nginx.ingress.kubernetes.io/rate-limit-window: "1m"
      nginx.ingress.kubernetes.io/client-max-body-size: "100m"

backend:
  ingress:
    annotations:
      nginx.ingress.kubernetes.io/rate-limit: "1000"
      nginx.ingress.kubernetes.io/rate-limit-window: "1m"
      nginx.ingress.kubernetes.io/proxy-body-size: "500m"
      nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
```

## 🔒 Security Configuration

### Service Account with Azure Workload Identity

```yaml
backend:
  serviceAccount:
    create: true
    name: "ai-studio-backend-sa"
    annotations:
      azure.workload.identity/client-id: "12345678-1234-1234-1234-123456789012"
      azure.workload.identity/tenant-id: "87654321-4321-4321-4321-210987654321"

# Pod security context
podSecurityContext:
  fsGroup: 1001
  runAsNonRoot: true
  runAsUser: 1001

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: false
  runAsNonRoot: true
  runAsUser: 1001
```

### Secrets Management

```bash
# Create secret with database connection string
kubectl create secret generic ai-studio-secrets \
  --from-literal=database-url="postgresql://user:password@host:5432/database" \
  --namespace ai-studio

# Create secret with TLS certificates
kubectl create secret tls ai-studio-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  --namespace ai-studio
```

## 📊 Monitoring and Observability

### Health Checks

The chart includes comprehensive health checks:

```yaml
# Frontend health checks
frontend:
  livenessProbe:
    httpGet:
      path: /
      port: 3000
    initialDelaySeconds: 30
    periodSeconds: 10

  readinessProbe:
    httpGet:
      path: /
      port: 3000
    initialDelaySeconds: 5
    periodSeconds: 5

# Backend health checks
backend:
  livenessProbe:
    httpGet:
      path: /api/v1/health
      port: 7860
    initialDelaySeconds: 60
    periodSeconds: 30

  readinessProbe:
    httpGet:
      path: /api/v1/health
      port: 7860
    initialDelaySeconds: 30
    periodSeconds: 10
```

### Resource Monitoring

```yaml
# Enable monitoring annotations
podAnnotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8080"
  prometheus.io/path: "/metrics"
```

## 🔄 Deployment Strategies

### Rolling Updates

```bash
# Update with new image version
helm upgrade ai-studio helmcharts/ai-studio/ \
  --set frontend.image.tag=v1.1.0 \
  --set backend.image.tag=v1.1.0

# Update with zero downtime
helm upgrade ai-studio helmcharts/ai-studio/ \
  --set frontend.image.tag=v1.1.0 \
  --wait --timeout=10m
```

### Blue-Green Deployment

```bash
# Deploy to staging environment
helm install ai-studio-staging helmcharts/ai-studio/ \
  -f values-staging.yaml \
  --namespace ai-studio-staging

# Promote to production
helm upgrade ai-studio helmcharts/ai-studio/ \
  -f values-production.yaml \
  --namespace ai-studio-production
```

### Canary Deployment

```yaml
# Canary deployment with Istio
frontend:
  replicaCount: 3
  image:
    tag: "v1.1.0"

# Add canary configuration
canary:
  enabled: true
  weight: 10  # 10% of traffic to new version
```

## 🧪 Testing

### Helm Tests

```bash
# Run built-in connection tests
helm test ai-studio

# Run with verbose output
helm test ai-studio --logs
```

### Custom Test Values

```yaml
# test-values.yaml
frontend:
  replicaCount: 1
  resources:
    limits:
      cpu: 500m
      memory: 512Mi

backend:
  replicaCount: 1
  resources:
    limits:
      cpu: 1
      memory: 2Gi
  persistence:
    enabled: false
```

```bash
# Test deployment with minimal resources
helm install ai-studio-test helmcharts/ai-studio/ \
  -f test-values.yaml \
  --namespace ai-studio-test \
  --create-namespace
```

## 🚨 Troubleshooting

### Common Issues

**1. Image Pull Errors**
```bash
# Check image pull secrets
kubectl get secrets -n ai-studio | grep docker

# Verify registry access
kubectl describe pod <pod-name> -n ai-studio
```

**2. Resource Constraints**
```bash
# Check resource usage
kubectl top pods -n ai-studio

# Check resource limits
kubectl describe pod <pod-name> -n ai-studio | grep -A 10 Resources
```

**3. Persistent Volume Issues**
```bash
# Check PVC status
kubectl get pvc -n ai-studio

# Check storage class
kubectl get storageclass
```

### Debug Commands

```bash
# Check chart values
helm get values ai-studio

# Render templates locally
helm template ai-studio helmcharts/ai-studio/ --debug

# Check deployment status
kubectl rollout status deployment/ai-studio-frontend -n ai-studio
kubectl rollout status deployment/ai-studio-backend -n ai-studio

# View logs
kubectl logs -l app.kubernetes.io/component=frontend -n ai-studio
kubectl logs -l app.kubernetes.io/component=backend -n ai-studio

# Port forward for local access
kubectl port-forward service/ai-studio-frontend 3000:3000 -n ai-studio
kubectl port-forward service/ai-studio-backend 7860:7860 -n ai-studio
```

## 📈 Performance Tuning

### Resource Optimization

```yaml
# High-performance configuration
frontend:
  resources:
    limits:
      cpu: 2
      memory: 2Gi
    requests:
      cpu: 1
      memory: 1Gi

backend:
  resources:
    limits:
      cpu: 4
      memory: 16Gi
    requests:
      cpu: 2
      memory: 8Gi

# High-throughput auto-scaling
backend:
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 20
    targetCPUUtilizationPercentage: 60
    targetMemoryUtilizationPercentage: 70
```

### Node Affinity

```yaml
# Schedule backend pods on high-memory nodes
backend:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          preference:
            matchExpressions:
              - key: node-type
                operator: In
                values:
                  - high-memory

# Anti-affinity for high availability
backend:
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchExpressions:
                - key: app.kubernetes.io/component
                  operator: In
                  values:
                    - backend
            topologyKey: kubernetes.io/hostname
```

## 🔧 Maintenance

### Backup and Recovery

```bash
# Backup persistent volumes
kubectl get pvc -n ai-studio
# Use your backup solution to backup PVs

# Backup Helm release
helm get all ai-studio > ai-studio-backup.yaml

# Restore from backup
helm install ai-studio-restored helmcharts/ai-studio/ \
  -f restore-values.yaml
```

### Updates and Upgrades

```bash
# Check for chart updates
helm repo update

# Upgrade chart version
helm upgrade ai-studio helmcharts/ai-studio/ \
  --reuse-values

# Rollback if needed
helm rollback ai-studio 1
```

## 📞 Support

For Helm chart related issues:

1. Check the [troubleshooting section](#troubleshooting)
2. Review Kubernetes events: `kubectl get events -n ai-studio`
3. Check pod logs: `kubectl logs -l app.kubernetes.io/name=ai-studio -n ai-studio`
4. Consult the [DEVELOPMENT.md](./DEVELOPMENT.md) for local development
5. Contact the AI Studio team via Slack #ai-studio-support

---

*Last Updated: October 2024*
*Chart Version: 0.1.0*
*Kubernetes Compatibility: 1.20+*