# Fix: Add Frontend and Backend Component Image Builds to Release Workflow

## 🐛 Problem Description

**Issue:** [#10215 - Missing langflow-frontend Docker Image for Version 1.6.4](https://github.com/langflow-ai/langflow/issues/10215)

When Langflow releases a new version (like 1.6.4), the corresponding `langflowai/langflow-frontend` Docker image is not being published to Docker Hub. This creates a version mismatch problem for users who rely on the separate frontend image, particularly those using the [langflow-ide Helm chart](https://github.com/langflow-ai/langflow-helm-charts/tree/main/charts/langflow-ide).

### Current Situation
- ✅ Main Langflow image (`langflowai/langflow`) gets published successfully
- ✅ Langflow EP image (`langflowai/langflow-ep`) gets published successfully
- ✅ Langflow All image (`langflowai/langflow-all`) gets published successfully
- ❌ Frontend component image (`langflowai/langflow-frontend`) is **NOT** being published
- ❌ Backend component image (`langflowai/langflow-backend`) is **NOT** being published

### Impact
Users deploying Langflow using the Helm chart that depends on separate frontend/backend images cannot upgrade to the latest versions. The last available frontend image on Docker Hub is still `1.5.1`, while the main Langflow release is at `1.6.4`.

## 🔍 Root Cause Analysis

The issue stems from the migration to the new `docker-build-v2.yml` workflow. Here's what happened:

### Old Workflow (`docker-build.yml`)
The previous workflow included a `build_components` job that:
- Built separate `langflow-frontend` and `langflow-backend` images
- Published them to both Docker Hub and GitHub Container Registry
- Supported multi-architecture builds (amd64/arm64)

### New Workflow (`docker-build-v2.yml`)
The newer workflow (which is now used by `release.yml`) focused on building the main images but **did not include the component build job**. This was an oversight during the workflow refactoring.

**Result:** When releases are triggered, only the main images get built, leaving the frontend and backend component images un-updated.

## ✨ The Fix

I've added a new job `build-frontend-backend-components` to `.github/workflows/docker-build-v2.yml` that:

### What It Does
1. **Triggers on Main Releases:** Only runs when `release_type == 'main'` and `push_to_registry == true`
2. **Builds All Component Combinations:** Creates 4 images in a matrix strategy:
   - `langflowai/langflow-backend` (Docker Hub)
   - `langflowai/langflow-frontend` (Docker Hub)
   - `ghcr.io/langflow-ai/langflow-backend` (GitHub Container Registry)
   - `ghcr.io/langflow-ai/langflow-frontend` (GitHub Container Registry)

3. **Multi-Architecture Support:** Builds for both `linux/amd64` and `linux/arm64` platforms

4. **Proper Tagging:**
   - For regular releases: Tags with version number AND `latest` (e.g., `1.6.4` and `latest`)
   - For pre-releases: Tags with version number only (e.g., `1.6.4`)

5. **Dependency Management:**
   - Waits for the main `langflow` image to be built first (via `needs: [build-main, create-manifest]`)
   - Adds a 120-second propagation delay to ensure the base image is available
   - Uses retry logic (3 attempts) to handle transient failures

### Technical Implementation Details

```yaml
build-frontend-backend-components:
  name: Build Frontend and Backend Components
  if: ${{ inputs.release_type == 'main' && inputs.push_to_registry }}
  runs-on: [self-hosted, linux, ARM64, langflow-ai-arm64-40gb]
  permissions:
    packages: write
  needs: [build-main, create-manifest]
  strategy:
    matrix:
      component: [docker-backend, docker-frontend, ghcr-backend, ghcr-frontend]
      include:
        - component: docker-backend
          dockerfile: ./docker/build_and_push_backend.Dockerfile
          registry: docker.io
          image_name: langflowai/langflow-backend
        - component: docker-frontend
          dockerfile: ./docker/frontend/build_and_push_frontend.Dockerfile
          registry: docker.io
          image_name: langflowai/langflow-frontend
        # ... (GHCR variants)
```

**Key Features:**
- ✅ Uses the same ARM64 self-hosted runner for consistency
- ✅ Extracts version dynamically from `uv tree` output
- ✅ Respects `pre_release` flag for tagging behavior
- ✅ Includes Docker cleanup to manage disk space
- ✅ Uses BuildKit caching for faster builds
- ✅ Proper authentication for both Docker Hub and GHCR

### Build Arguments
The backend image requires the base Langflow image:
```dockerfile
ARG LANGFLOW_IMAGE
FROM $LANGFLOW_IMAGE
```

The workflow correctly provides this:
```yaml
build-args: |
  LANGFLOW_IMAGE=${{ matrix.registry == 'docker.io' && 'langflowai' || 'ghcr.io/langflow-ai' }}/langflow:${{ steps.version.outputs.version }}
```

## 🧪 Testing Strategy

### What I've Verified
1. ✅ **YAML Syntax:** Validated with Python's `yaml.safe_load()` - no syntax errors
2. ✅ **Workflow Logic:** Reviewed job dependencies, conditions, and matrix strategy
3. ✅ **Dockerfile Compatibility:** Confirmed both Dockerfiles exist and have correct build args
4. ✅ **Version Extraction:** The version extraction logic matches other jobs in the workflow
5. ✅ **Registry Logic:** Conditional login based on registry matches the pattern used elsewhere

### How to Test the Fix (Post-Merge)
When the next Langflow release is triggered:

1. **Trigger a Release:**
   ```bash
   # Via GitHub UI: Actions → Langflow Release workflow
   # Set inputs:
   #   - release_tag: v1.6.5 (or next version)
   #   - build_docker_main: true
   #   - dry_run: false
   ```

2. **Check Workflow Execution:**
   - Verify the `build-frontend-backend-components` job runs
   - Confirm all 4 matrix components (docker-backend, docker-frontend, ghcr-backend, ghcr-frontend) build successfully
   - Check for multi-arch manifest creation

3. **Verify Images on Docker Hub:**
   ```bash
   # Check frontend image
   docker pull langflowai/langflow-frontend:1.6.5
   docker pull langflowai/langflow-frontend:latest

   # Check backend image
   docker pull langflowai/langflow-backend:1.6.5
   docker pull langflowai/langflow-backend:latest
   ```

4. **Verify Images on GHCR:**
   ```bash
   docker pull ghcr.io/langflow-ai/langflow-frontend:1.6.5
   docker pull ghcr.io/langflow-ai/langflow-backend:1.6.5
   ```

5. **Test Helm Chart Integration:**
   ```bash
   # Update Helm chart to use new version
   helm upgrade langflow langflow-ide \
     --set frontend.image.tag=1.6.5 \
     --set backend.image.tag=1.6.5
   ```

## 📋 Checklist

- [x] Root cause identified and documented
- [x] Fix implemented in `docker-build-v2.yml`
- [x] YAML syntax validated
- [x] Job dependencies correctly configured
- [x] Multi-architecture support included
- [x] Both Docker Hub and GHCR registries covered
- [x] Build arguments properly passed
- [x] Retry logic added for reliability
- [x] Pre-release tagging behavior respected
- [x] Documentation written (this PR description)

## 🎯 Expected Outcome

After this PR is merged and the next release is triggered:

1. ✅ `langflowai/langflow-frontend:<version>` will be published to Docker Hub
2. ✅ `langflowai/langflow-backend:<version>` will be published to Docker Hub
3. ✅ Both images will also be published to GHCR
4. ✅ Multi-arch manifests (amd64 + arm64) will be available
5. ✅ The `latest` tags will be updated (for non-pre-releases)
6. ✅ Helm chart users can upgrade to the latest Langflow versions

## 🔗 Related Issues

- Fixes #10215 - Missing langflow-frontend Docker Image for Version 1.6.4

## 📝 Notes for Reviewers

1. **No Breaking Changes:** This only adds a new job - existing functionality is unchanged
2. **Consistent Pattern:** The implementation follows the same patterns used in the old `docker-build.yml` workflow
3. **Resource Usage:** Uses the same ARM64 self-hosted runner that's already used for main builds
4. **Backward Compatible:** Doesn't affect existing deployments or images

## 🙏 Acknowledgments

Thanks to @Vasyl-Prokopenko for reporting this issue and providing clear details about the impact on Helm chart deployments!

---

**Ready for Review! 🚀**

Once this is merged, the next Langflow release will automatically publish the frontend and backend component images, resolving the version mismatch issue for Helm chart users.
