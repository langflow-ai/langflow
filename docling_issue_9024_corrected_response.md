# Response for Issue #9024: Docling Build Failed

Hi @brunorafaeI,

Thank you for reporting this Docling issue. I've analyzed the codebase and identified the root cause along with working solutions.

## Analysis

This is a confirmed issue in Langflow when using Docling components with Docker deployments. The issue has multiple phases:

1. **Installation Error**: The Docker image doesn't include Docling in runtime dependencies
2. **Memory/SIGKILL Errors**: After manual installation, worker processes crash due to memory issues during Docling model loading

## Current Status

Based on the codebase analysis:
- **PR #9393** (merged August 20, 2025): Implements worker process isolation for Docling
- **PR #9469** (merged August 22, 2025): Moves Docling to development dependencies  
- **PR #9398** (merged August 22, 2025): Adds advanced Docling parsing features

These changes are already in the main branch but **the release timeline depends on the Langflow team's decisions**.

## Working Solutions

### Option 1: Docker Runtime Installation (Temporary)
For quick testing, install Docling directly in the running container:

1. Start your Langflow Docker container:
```bash
docker run -p 7860:7860 langflowai/langflow:1.5.0.post2
```

2. Access the container:
```bash
docker exec -it <container_id> bash
```

3. Install Docling:
```bash
uv pip install docling
```

4. Restart the container for the changes to take effect

**Note**: This installation will be lost when the container is recreated.

### Option 2: Custom Docker Image (Recommended)
Create a custom Dockerfile for persistent Docling support:

```dockerfile
FROM langflowai/langflow:1.5.0.post2

# Install Docling
RUN uv pip install docling

EXPOSE 7860
CMD ["langflow", "run"]
```

Build and run:
```bash
docker build -t langflow-docling .
docker run -m 4g -p 7860:7860 langflow-docling
```

## Memory Requirements

The SIGKILL errors are related to:
- Heavy memory usage during Docling model initialization
- Docker container memory limits

**Recommended configuration:**
- Allocate at least 4GB of memory to the Docker container
- Use the `-m 4g` flag when running Docker:
```bash
docker run -m 4g -p 7860:7860 your-image-name
```

## Technical Details

The merged fixes implement:
- Process isolation using `multiprocessing` to prevent crashes
- Proper signal handling (SIGTERM/SIGKILL) for graceful shutdown
- Error propagation between worker and main processes
- Memory-efficient processing pipeline

## Notes

- The fixes are in the main branch as of August 22, 2025
- For production use, the custom Docker image approach is recommended
- Monitor your container's memory usage during Docling operations

Let me know if you encounter any issues with these solutions.

Best regards,  
Langflow Support