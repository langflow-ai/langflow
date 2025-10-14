# AI Studio Azure DevOps Organization Guide

This document provides detailed information about the reorganized Azure DevOps structure and pipeline integration with the unified Helm chart.

## 📁 Reorganized Structure

```
ai-studio/
├── .azure-pipelines/
│   ├── backend-cicd.yaml                   # Backend CI/CD pipeline
│   ├── frontend-cicd.yaml                  # Frontend CI/CD pipeline
│   ├── templates/
│   │   ├── backend-build-template.yml      # Backend build template
│   │   ├── frontend-build-template.yml     # Frontend build template
│   │   └── release-template.yml            # Release template
│   └── variables/
│       └── common.yml                      # Common variables
└── docs/
    ├── AZURE_DEVOPS.md                     # This document
    └── HELM.md                             # Helm chart documentation
```

## 🚀 Pipeline Architecture

### Dual Pipeline Strategy

The reorganized structure maintains the **dual pipeline approach** for optimal efficiency:

1. **Backend Pipeline** (`.azure-pipelines/backend-cicd.yaml`)
   - Triggers on: `src/backend/**`, `pyproject.toml`, `uv.lock`, `docker/backend/**`
   - Builds: Python backend with Langflow and Genesis components
   - Output: `sprintregistry.azurecr.io/ai-studio-backend:${BUILD_ID}`
   - Stages: Build → UpdatePlatformCharts

2. **Frontend Pipeline** (`.azure-pipelines/frontend-cicd.yaml`)
   - Triggers on: `src/frontend/**`, `docker/frontend/**`
   - Builds: React/TypeScript frontend with Vite
   - Output: `sprintregistry.azurecr.io/ai-studio-frontend:${BUILD_ID}`
   - Stages: Build → UpdatePlatformCharts

### Pipeline Templates

#### Build Templates

Build templates handle Docker image build and push operations:

- `backend-build-template.yml` - Backend Docker build
- `frontend-build-template.yml` - Frontend Docker build

```yaml
# Usage in pipeline
- template: templates/backend-build-template.yml
  parameters:
    CONTAINER_NAME: $(IMAGE_NAME)
    DOCKERFILE_PATH: $(DOCKERFILE_PATH)
    AZURE_CONTAINER_REGISTRY: $(AZURE_CONTAINER_REGISTRY)
    BUILD_ARGS: |
      --build-arg BUILD_VERSION=$(Build.BuildNumber)
```

#### Release Template

The release template (`templates/release-template.yml`) updates platform-charts repository for ArgoCD deployment:

```yaml
# Usage in pipeline
- template: templates/release-template.yml
  parameters:
    SERVICE_NAME: 'backend'
    IMAGE_NAME: $(IMAGE_NAME)
```

## ⚙️ Pipeline Configuration

### Updated Pipeline Files

Both pipeline files have been updated to reference their new locations:

```yaml
# Updated trigger paths
trigger:
  paths:
    include:
      - .azure-pipelines/backend-cicd.yaml
      - .azure-pipelines/templates/*backend*

pr:
  paths:
    include:
      - .azure-pipelines/backend-cicd.yaml
      - .azure-pipelines/templates/*backend*
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
# .azure-pipelines/deploy.yaml
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
   # From: azure-devops/pipelines/azure-pipelines-backend.yml
   # To: .azure-pipelines/backend-cicd.yaml
   ```

2. **Update Trigger Paths**
   ```yaml
   # Update all pipeline trigger paths to reference new locations
   trigger:
     paths:
       include:
         - .azure-pipelines/backend-cicd.yaml
         - .azure-pipelines/templates/*backend*
   ```

3. **Simplified Pipeline Structure**
   ```yaml
   # Pipelines now focus on build and release stages only
   stages:
   - stage: Build
     jobs:
     - template: templates/backend-build-template.yml
   
   - stage: UpdatePlatformCharts
     jobs:
     - template: templates/release-template.yml
   ```

### Testing Migration

```bash
# 1. Validate pipeline syntax
az pipelines validate --repository ai-studio --yaml-path .azure-pipelines/backend-cicd.yaml

# 2. Check pipeline structure
cat .azure-pipelines/backend-cicd.yaml

# 3. Verify template files exist
ls -la .azure-pipelines/templates/
```

## 🚨 Troubleshooting

### Common Migration Issues

**1. Pipeline File Not Found**
```
Error: Pipeline file 'azure-pipelines-backend.yml' not found
```
*Solution*: Update Azure DevOps pipeline definition to point to `.azure-pipelines/backend-cicd.yaml`

**2. Template Path Errors**
```
Error: Template 'templates/backend-build-template.yml' not found
```
*Solution*: Ensure templates exist in `.azure-pipelines/templates/` directory

**3. Variable Resolution Issues**
```
Error: Variable 'ACR_NAME' not found
```
*Solution*: Variables are defined directly in pipeline files or can import from `variables/common.yml`

### Debug Commands

```bash
# Check Azure DevOps pipeline status
az pipelines list --organization https://dev.azure.com/yourorg --project ai-studio

# Validate pipeline YAML
az pipelines validate --repository ai-studio --yaml-path .azure-pipelines/backend-cicd.yaml

# Check pipeline files
ls -la .azure-pipelines/
ls -la .azure-pipelines/templates/
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