# AI Studio Azure DevOps Organization Guide

This document provides detailed information about the reorganized Azure DevOps structure and pipeline integration with the unified Helm chart.

## 📁 Reorganized Structure

```
ai-studio/
├── azure-devops/
│   ├── pipelines/
│   │   ├── azure-pipelines-backend.yml     # Backend CI/CD pipeline
│   │   └── azure-pipelines-frontend.yml    # Frontend CI/CD pipeline
│   ├── templates/
│   │   ├── docker-build-template.yml       # Docker build template
│   │   └── helm-deploy-template.yml        # Helm deployment template
│   └── variables/
│       └── common.yml                      # Common variables
├── helmcharts/ai-studio/                   # Unified Helm chart
└── docs/
    ├── AZURE_DEVOPS.md                     # This document
    └── HELM.md                             # Helm chart documentation
```

## 🚀 Pipeline Architecture

### Dual Pipeline Strategy

The reorganized structure maintains the **dual pipeline approach** for optimal efficiency:

1. **Backend Pipeline** (`azure-devops/pipelines/azure-pipelines-backend.yml`)
   - Triggers on: `src/backend/**`, `pyproject.toml`, `uv.lock`, `docker/backend/**`
   - Builds: Python backend with Langflow and Genesis components
   - Output: `aistudioregistry.azurecr.io/ai-studio-backend:${BUILD_ID}`

2. **Frontend Pipeline** (`azure-devops/pipelines/azure-pipelines-frontend.yml`)
   - Triggers on: `src/frontend/**`, `docker/frontend/**`
   - Builds: React/TypeScript frontend with Vite
   - Output: `aistudioregistry.azurecr.io/ai-studio-frontend:${BUILD_ID}`

### Pipeline Templates

#### Docker Build Template (`templates/docker-build-template.yml`)

Standardized Docker build and push operations:

```yaml
# Usage in pipeline
- template: ../templates/docker-build-template.yml
  parameters:
    serviceName: 'backend'
    dockerfilePath: 'docker/backend/Dockerfile'
    buildArgs:
      BUILD_VERSION: $(Build.BuildId)
      PYTHON_VERSION: $(PYTHON_VERSION)
```

#### Helm Deploy Template (`templates/helm-deploy-template.yml`)

Unified deployment using the AI Studio Helm chart:

```yaml
# Usage in pipeline
- template: ../templates/helm-deploy-template.yml
  parameters:
    environment: 'development'
    namespace: 'ai-studio-dev'
    valuesFile: 'environments/dev-values.yaml'
    setValues:
      frontend.image.tag: $(Build.BuildId)
      backend.image.tag: $(Build.BuildId)
```

## ⚙️ Pipeline Configuration

### Updated Pipeline Files

Both pipeline files have been updated to reference their new locations:

```yaml
# Updated trigger paths
trigger:
  paths:
    include:
      - azure-devops/pipelines/azure-pipelines-backend.yml  # Updated path

pr:
  paths:
    include:
      - azure-devops/pipelines/azure-pipelines-backend.yml  # Updated path
```

### Common Variables

Centralized variables in `variables/common.yml`:

```yaml
variables:
  # Container Registry
  ACR_NAME: 'aistudioregistry'
  ACR_ENDPOINT: 'aistudioregistry.azurecr.io'

  # Runtime Versions
  NODE_VERSION: '20.x'
  PYTHON_VERSION: '3.12'
  UV_VERSION: '0.4.0'

  # Helm Configuration
  HELM_VERSION: '3.12.0'
  CHART_PATH: 'helmcharts/ai-studio'

  # Deployment Namespaces
  DEV_NAMESPACE: 'ai-studio-dev'
  STAGING_NAMESPACE: 'ai-studio-staging'
  PROD_NAMESPACE: 'ai-studio-prod'
```

## 🔄 Integration with Helm Chart

### Automated Deployment Pipeline

Create a new deployment pipeline that uses the unified Helm chart:

```yaml
# azure-devops/pipelines/azure-pipelines-deploy.yml
trigger: none

pr: none

variables:
  - template: ../variables/common.yml

parameters:
  - name: environment
    displayName: 'Target Environment'
    type: string
    default: 'development'
    values:
      - development
      - staging
      - production
  - name: frontendImageTag
    displayName: 'Frontend Image Tag'
    type: string
    default: 'latest'
  - name: backendImageTag
    displayName: 'Backend Image Tag'
    type: string
    default: 'latest'

stages:
  - stage: Deploy
    displayName: 'Deploy AI Studio'
    jobs:
      - deployment: DeployToK8s
        displayName: 'Deploy to Kubernetes'
        environment: '${{ parameters.environment }}'
        strategy:
          runOnce:
            deploy:
              steps:
                - template: ../templates/helm-deploy-template.yml
                  parameters:
                    environment: '${{ parameters.environment }}'
                    namespace: 'ai-studio-${{ parameters.environment }}'
                    setValues:
                      frontend.image.tag: '${{ parameters.frontendImageTag }}'
                      backend.image.tag: '${{ parameters.backendImageTag }}'
                      global.environment: '${{ parameters.environment }}'
```

### Environment-Specific Values

Create environment-specific values files:

```yaml
# environments/dev-values.yaml
global:
  environment: "development"

frontend:
  replicaCount: 1
  resources:
    limits:
      cpu: 500m
      memory: 1Gi

backend:
  replicaCount: 1
  resources:
    limits:
      cpu: 1
      memory: 2Gi
  persistence:
    enabled: false  # Use ephemeral storage for dev

# environments/prod-values.yaml
global:
  environment: "production"

frontend:
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10

backend:
  replicaCount: 5
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 20
  persistence:
    enabled: true
    size: 100Gi
    storageClass: "premium-ssd"
```

## 🔒 Security and Access Control

### Service Connections

Required Azure DevOps service connections:

1. **Azure Container Registry**
   - Name: `aistudioregistry`
   - Type: Docker Registry
   - Registry URL: `aistudioregistry.azurecr.io`

2. **Kubernetes Clusters**
   - Development: `ai-studio-dev-k8s`
   - Staging: `ai-studio-staging-k8s`
   - Production: `ai-studio-prod-k8s`

3. **Azure Resource Manager**
   - For Azure services integration
   - Managed identity authentication preferred

### Pipeline Security

```yaml
# Security scanning in templates
- task: CmdLine@2
  displayName: 'Security Scan with Trivy'
  inputs:
    script: |
      # Install and run Trivy
      trivy image --exit-code 0 --severity HIGH,CRITICAL \
        $(ACR_ENDPOINT)/$(IMAGE_NAME):$(Build.BuildId)
```

## 📊 Monitoring and Observability

### Pipeline Metrics

Monitor these key metrics:

- **Build Success Rate**: Target >95%
- **Build Duration**:
  - Backend: <15 minutes
  - Frontend: <12 minutes
  - Deployment: <5 minutes
- **Deployment Success Rate**: Target >98%

### Deployment Tracking

```yaml
# Add deployment annotations to track releases
- task: Kubernetes@1
  displayName: 'Annotate Deployment'
  inputs:
    command: 'annotate'
    arguments: >
      deployment/ai-studio-backend
      deployment.kubernetes.io/revision="$(Build.BuildId)"
      deployment.kubernetes.io/build-url="$(Build.BuildUri)"
      deployment.kubernetes.io/commit="$(Build.SourceVersion)"
```

### Notifications

Configure Slack notifications:

```yaml
- task: SlackNotification@1
  condition: always()
  inputs:
    SlackApiToken: $(SLACK_TOKEN)
    Channel: '#ai-studio-deployments'
    Message: |
      🚀 AI Studio Deployment
      Environment: $(ENVIRONMENT)
      Status: $(Agent.JobStatus)
      Frontend: $(FRONTEND_IMAGE_TAG)
      Backend: $(BACKEND_IMAGE_TAG)
      Build: $(Build.BuildNumber)
```

## 🔄 Migration Guide

### Updating Existing Pipelines

1. **Update Pipeline References**
   ```bash
   # In Azure DevOps, update pipeline file paths:
   # From: azure-pipelines-backend.yml
   # To: azure-devops/pipelines/azure-pipelines-backend.yml
   ```

2. **Update Trigger Paths**
   ```yaml
   # Update all pipeline trigger paths to reference new locations
   trigger:
     paths:
       include:
         - azure-devops/pipelines/azure-pipelines-backend.yml
   ```

3. **Migrate to Templates**
   ```yaml
   # Replace inline build steps with template calls
   - template: ../templates/docker-build-template.yml
     parameters:
       serviceName: 'backend'
       dockerfilePath: 'docker/backend/Dockerfile'
   ```

### Testing Migration

```bash
# 1. Validate pipeline syntax
az pipelines validate --repository ai-studio --yaml-path azure-devops/pipelines/azure-pipelines-backend.yml

# 2. Test template rendering
helm template ai-studio helmcharts/ai-studio/ --debug

# 3. Run test deployment
helm install ai-studio-test helmcharts/ai-studio/ \
  --namespace ai-studio-test \
  --create-namespace \
  --dry-run
```

## 🚨 Troubleshooting

### Common Migration Issues

**1. Pipeline File Not Found**
```
Error: Pipeline file 'azure-pipelines-backend.yml' not found
```
*Solution*: Update Azure DevOps pipeline definition to point to new path

**2. Template Path Errors**
```
Error: Template 'templates/docker-build-template.yml' not found
```
*Solution*: Use relative paths from pipeline file location (`../templates/`)

**3. Variable Resolution Issues**
```
Error: Variable 'ACR_NAME' not found
```
*Solution*: Import common variables template in each pipeline

### Debug Commands

```bash
# Check Azure DevOps pipeline status
az pipelines list --organization https://dev.azure.com/yourorg --project ai-studio

# Validate pipeline YAML
az pipelines validate --repository ai-studio --yaml-path azure-devops/pipelines/azure-pipelines-backend.yml

# Test Helm chart deployment
helm install ai-studio-debug helmcharts/ai-studio/ \
  --namespace ai-studio-debug \
  --create-namespace \
  --set frontend.image.tag=debug \
  --set backend.image.tag=debug \
  --dry-run --debug
```

## 📈 Performance Optimizations

### Build Caching

```yaml
# Enhanced caching in templates
- task: Cache@2
  inputs:
    key: 'docker-layers | "$(Agent.OS)" | $(DOCKERFILE_PATH)'
    path: /tmp/.buildx-cache
    cacheHitVar: CACHE_RESTORED
  displayName: 'Cache Docker layers'
```

### Parallel Execution

```yaml
# Run frontend and backend builds in parallel
strategy:
  matrix:
    frontend:
      SERVICE_NAME: 'frontend'
      DOCKERFILE_PATH: 'docker/frontend/Dockerfile'
    backend:
      SERVICE_NAME: 'backend'
      DOCKERFILE_PATH: 'docker/backend/Dockerfile'
  maxParallel: 2
```

## 📞 Support and Maintenance

### Pipeline Support

1. **Issues**: Contact DevOps team via #ai-studio-devops Slack channel
2. **Emergency**: Page on-call engineer for production deployment issues
3. **Templates**: Submit PR for template improvements
4. **Variables**: Request variable updates via ServiceNow

### Regular Maintenance

- **Weekly**: Review pipeline performance metrics
- **Monthly**: Update base images and dependencies
- **Quarterly**: Security audit of service connections and permissions

### Useful Links

- [Azure DevOps Documentation](https://docs.microsoft.com/en-us/azure/devops/)
- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/)
- [Kubernetes Deployment Strategies](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)

---

*Last Updated: October 2024*
*Azure DevOps Version: 2022+*
*Pipeline Schema: v1.0*