# AI Studio Azure DevOps Pipelines Guide

This document explains the Azure DevOps pipeline structure, triggers, and deployment strategy for the AI Studio monorepo.

## 📁 Pipeline Structure

```
ai-studio/
├── azure-pipelines-backend.yml     # Backend CI/CD pipeline
├── azure-pipelines-frontend.yml    # Frontend CI/CD pipeline
└── .azure-pipelines/
    ├── templates/                   # Shared pipeline templates
    └── variables/                   # Pipeline variable groups
```

## 🚀 Pipeline Strategy

### Dual Pipeline Approach

We use **two separate pipelines** instead of a single monolithic pipeline for the following benefits:

1. **🎯 Targeted Triggers**: Only relevant pipeline runs when specific code changes
2. **⚡ Faster Feedback**: Reduced pipeline execution time
3. **🔧 Independent Teams**: Frontend and backend teams work independently
4. **🐛 Easier Debugging**: Issues isolated to specific service
5. **💰 Cost Efficiency**: Fewer compute resources wasted

### Path-Based Triggering

Both pipelines use intelligent path-based triggers to determine when to run:

#### Backend Pipeline Triggers (`azure-pipelines-backend.yml`)
```yaml
trigger:
  paths:
    include:
      - src/backend/**
      - pyproject.toml
      - uv.lock
      - docker/backend/**
      - azure-pipelines-backend.yml
```

#### Frontend Pipeline Triggers (`azure-pipelines-frontend.yml`)
```yaml
trigger:
  paths:
    include:
      - src/frontend/**
      - docker/frontend/**
      - azure-pipelines-frontend.yml
```

## 🔄 Pipeline Stages

### Backend Pipeline (`azure-pipelines-backend.yml`)

#### Stage 1: Test and Validate
**Condition**: Pull Request only
**Duration**: ~5-8 minutes

```yaml
- Python 3.12 setup and uv installation
- Dependency installation with uv sync
- Backend tests with pytest
- Code linting with ruff
- Genesis module tests
```

**Key Features:**
- ✅ Genesis spec-to-flow conversion tests
- ✅ Langflow component validation
- ✅ Code quality checks with ruff
- ✅ Healthcare component testing

#### Stage 2: Build and Push
**Condition**: Main/Develop branch only
**Duration**: ~8-12 minutes

```yaml
- Docker image build with backend Dockerfile
- Image tagging with Build.BuildId and 'latest'
- Push to Azure Container Registry (ACR)
```

**Build Arguments:**
- `BUILD_VERSION`: Azure DevOps Build ID
- `PYTHON_VERSION`: Python runtime version

#### Stage 3: Security Scan
**Condition**: Main branch only
**Duration**: ~3-5 minutes

```yaml
- Container vulnerability scanning with Trivy
- Security report generation
- Critical/High severity issue reporting
```

#### Stage 4: Notification
**Condition**: Always runs
**Duration**: ~1 minute

```yaml
- Pipeline status summary
- Build artifact information
- Component inventory reporting
```

### Frontend Pipeline (`azure-pipelines-frontend.yml`)

#### Stage 1: Test and Validate
**Condition**: Pull Request only
**Duration**: ~6-10 minutes

```yaml
- Node.js 20.x setup
- npm dependency installation with caching
- TypeScript type checking
- ESLint code linting
- Unit tests with Jest
- Build validation
```

**Key Features:**
- ✅ React component testing
- ✅ TypeScript compilation validation
- ✅ Conversational UI component tests
- ✅ Agent builder interface validation

#### Stage 2: Build and Push
**Condition**: Main/Develop branch only
**Duration**: ~6-10 minutes

```yaml
- Docker image build with frontend Dockerfile
- Production build optimization
- Image tagging and registry push
```

**Build Arguments:**
- `BUILD_VERSION`: Azure DevOps Build ID
- `BACKEND_URL`: Production API endpoint
- `NODE_ENV`: Production environment

#### Stage 3: End-to-End Tests
**Condition**: Main branch only
**Duration**: ~8-15 minutes

```yaml
- Playwright E2E test execution
- Cross-browser compatibility testing
- User journey validation
- Test result publishing
```

#### Stage 4: Security Scan
**Condition**: Main branch only
**Duration**: ~3-5 minutes

```yaml
- npm security audit
- Container vulnerability scanning
- Dependency security validation
```

#### Stage 5: Notification
**Condition**: Always runs
**Duration**: ~1 minute

```yaml
- Pipeline status summary
- Deployment readiness report
- UI component inventory
```

## ⚙️ Pipeline Configuration

### Variables

Both pipelines use the following variable configuration:

#### Container Registry Variables
```yaml
ACR_NAME: 'aistudioregistry'           # Azure Container Registry name
IMAGE_NAME: 'ai-studio-[backend|frontend]' # Image repository name
DOCKERFILE_PATH: 'docker/[service]/Dockerfile' # Dockerfile location
```

#### Environment Variables
```yaml
# Backend
PYTHON_VERSION: '3.12'                # Python runtime version
UV_VERSION: '0.4.0'                   # uv package manager version

# Frontend
NODE_VERSION: '20.x'                  # Node.js runtime version
NPM_CACHE_FOLDER: '$(Pipeline.Workspace)/.npm' # npm cache location
```

### Service Connections

Required service connections in Azure DevOps:

1. **Azure Container Registry**: For image push/pull operations
2. **Azure Resource Manager**: For deployment to Azure services
3. **GitHub**: For repository access (if using GitHub)

### Pipeline Permissions

Recommended pipeline permissions:

- **Contribute**: Pipeline execution and status updates
- **Build**: Queue builds and access build artifacts
- **Release**: Deploy to staging and production environments

## 🎯 Trigger Logic

### Scenario-Based Triggering

| Scenario | Backend Pipeline | Frontend Pipeline | Reason |
|----------|-----------------|------------------|--------|
| Backend-only changes | ✅ Runs | ❌ Skipped | Efficient resource usage |
| Frontend-only changes | ❌ Skipped | ✅ Runs | Independent development |
| Both services changed | ✅ Runs | ✅ Runs | Parallel execution |
| Root config changes | ✅ Runs | ❌ Skipped | Backend dependencies |
| Pipeline file changes | ✅ Runs | ✅ Runs | Self-validation |

### Pull Request Validation

**PR Triggers:**
- All PRs to `main` and `develop` branches
- Only test and validation stages run
- No image building or deployment
- Fast feedback for code quality

**Branch Protection:**
- Require pipeline success before merge
- Require code review approval
- Require up-to-date branches

## 🚀 Deployment Strategy

### Image Tagging Strategy

```yaml
Tags:
  - $(Build.BuildId)     # Unique build identifier
  - latest               # Latest stable version
  - v$(Build.SourceBranchName) # Branch-based tagging
```

### Environment Promotion

1. **Development**: Automatic deployment on `develop` branch
2. **Staging**: Manual approval required
3. **Production**: Manual approval + additional validations

### Rollback Strategy

```bash
# Rollback to previous version
az container restart --resource-group ai-studio-rg --name ai-studio-backend
az container update --resource-group ai-studio-rg --name ai-studio-backend --image aistudioregistry.azurecr.io/ai-studio-backend:previous-build-id
```

## 📊 Pipeline Monitoring

### Pipeline Metrics

Monitor the following metrics for pipeline health:

- **Success Rate**: Target >95% success rate
- **Duration**: Backend <15min, Frontend <20min
- **Queue Time**: Target <2 minutes
- **Test Coverage**: Target >80% code coverage

### Performance Optimization

**Caching Strategy:**
- npm packages cached between builds
- Docker layer caching enabled
- Python dependencies cached with uv

**Parallel Execution:**
- Independent stage execution where possible
- Matrix builds for multiple environments
- Parallel test execution

### Alerts and Notifications

**Slack Integration:**
```yaml
# Add to pipeline success/failure notification
- task: SlackNotification@1
  inputs:
    SlackApiToken: $(SLACK_TOKEN)
    Channel: '#ai-studio-deployments'
    Message: '🚀 AI Studio deployment completed: $(Build.BuildNumber)'
```

**Email Notifications:**
- Pipeline failures automatically notify team leads
- Weekly pipeline health reports
- Security scan results for critical vulnerabilities

## 🐛 Troubleshooting

### Common Pipeline Issues

#### 1. Build Failures

**Symptom**: Docker build fails with dependency errors
```bash
# Debug locally
docker build -f docker/backend/Dockerfile . --progress=plain --no-cache

# Check dependency versions
uv pip list
npm list
```

**Solution**: Update dependency versions in lock files

#### 2. Test Failures

**Symptom**: Tests pass locally but fail in pipeline
```bash
# Check environment differences
env | grep -E "(NODE_ENV|PYTHON_PATH|LANGFLOW_)"

# Run tests in pipeline environment
docker run --rm -it ai-studio-backend:latest pytest src/backend/tests/
```

**Solution**: Ensure environment parity between local and pipeline

#### 3. Performance Issues

**Symptom**: Pipeline takes longer than expected
```yaml
# Add timing to investigate bottlenecks
- script: |
    echo "##[debug]Stage started: $(date)"
    # Your stage commands here
    echo "##[debug]Stage completed: $(date)"
```

**Solution**: Optimize Docker builds, enable caching, parallelize where possible

#### 4. Permission Issues

**Symptom**: Cannot push to registry or deploy
```bash
# Check service connection permissions
az acr login --name aistudioregistry
az account show
```

**Solution**: Verify service principal permissions and registry access

### Debug Commands

```bash
# Check pipeline variables
echo "Build ID: $(Build.BuildId)"
echo "Source Branch: $(Build.SourceBranch)"
echo "Build Reason: $(Build.Reason)"

# Container debugging
docker run --rm -it $(ACR_NAME).azurecr.io/$(IMAGE_NAME):$(Build.BuildId) /bin/bash

# Registry inspection
az acr repository show-tags --name $(ACR_NAME) --repository $(IMAGE_NAME)
```

### Log Analysis

**Pipeline Logs Location:**
- Azure DevOps: Build > Logs tab
- Downloaded logs: JSON format with timestamps
- Structured logging with correlation IDs

**Key Log Patterns:**
```bash
# Search for errors
grep -i error pipeline.log

# Find performance bottlenecks
grep -i "elapsed time\|duration" pipeline.log

# Security scan results
grep -i "high\|critical\|vulnerability" pipeline.log
```

## 🔒 Security and Compliance

### Security Scanning

**Container Security:**
- Trivy vulnerability scanning
- Base image security updates
- Secrets scanning with Azure Key Vault

**Code Security:**
- SAST (Static Application Security Testing)
- Dependency vulnerability checking
- License compliance validation

### Compliance Requirements

**Healthcare Compliance:**
- HIPAA-compliant pipeline environments
- Audit logging for all deployments
- Data encryption in transit and at rest

**Access Control:**
- Role-based pipeline permissions
- Service principal authentication
- Multi-factor authentication required

## 📞 Support and Maintenance

### Pipeline Maintenance

**Weekly Tasks:**
- Review pipeline performance metrics
- Update base images for security patches
- Validate test coverage reports

**Monthly Tasks:**
- Dependency updates (Python packages, npm packages)
- Security scan review and remediation
- Pipeline optimization opportunities

**Quarterly Tasks:**
- Azure DevOps extension updates
- Service connection rotation
- Disaster recovery testing

### Getting Help

**Pipeline Issues:**
1. Check the [troubleshooting section](#troubleshooting)
2. Review Azure DevOps pipeline logs
3. Consult team documentation in Confluence
4. Contact DevOps team via Slack #ai-studio-devops

**Emergency Escalation:**
- **Critical Production Issues**: Page on-call engineer
- **Security Incidents**: Follow security incident response plan
- **Data Issues**: Contact data engineering team immediately

---

*Last Updated: October 2024*
*Azure DevOps Version: 2022+*
*Pipeline YAML Schema: v1.0*