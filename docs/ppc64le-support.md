# IBM Power Systems (ppc64le) Support

Langflow now supports IBM Power Systems architecture (ppc64le) alongside AMD64 and ARM64 architectures.

## Overview

Starting from version 1.8.0, Langflow provides multi-architecture Docker images that include support for:
- `linux/amd64` (x86_64)
- `linux/arm64` (aarch64)
- `linux/ppc64le` (IBM Power Systems)

## Installation

### Docker (Recommended)

Pull the multi-architecture image:

```bash
docker pull langflowai/langflow:latest
```

Docker will automatically select the correct image for your architecture.

### Python Package

Install Langflow using uv or pip:

```bash
# Using uv (recommended)
uv pip install langflow

# Using pip
pip install langflow
```

## Architecture-Specific Considerations

### Supported Features on ppc64le

✅ **Fully Supported:**
- Core Langflow application and API
- Frontend UI (React-based)
- All major LLM integrations (OpenAI, Anthropic, Google, etc.)
- Vector stores: Pinecone, Weaviate, Qdrant, Supabase, Redis, Elasticsearch
- Database integrations: PostgreSQL, MongoDB, Cassandra, Couchbase
- Data processing and transformations
- Agent frameworks and tools
- Most Python-based components

### Limited or Unsupported Features on ppc64le

⚠️ **Limited Support:**
- **Local LLM inference** (`llama-cpp-python`, `ctransformers`): Not available due to lack of pre-built wheels. These packages require compilation from source.
- **FAISS vector store** (`faiss-cpu`): Not available in standard installation. May work if compiled from source.
- **OCR features** (`tesserocr`, `easyocr`): Excluded on ppc64le due to missing native dependencies.
- **Browser automation** (Playwright): Limited browser binary availability on ppc64le.

### IBM Power Wheel Repository

Langflow automatically uses IBM's Power wheel repository for packages that have ppc64le-specific builds:

```
https://wheels.developerfirst.ibm.com/ppc64le/linux
```

This repository is automatically configured when installing on ppc64le systems.

## Building from Source on ppc64le

### Prerequisites

- IBM Power system running Linux (RHEL, Ubuntu, or SLES)
- Python 3.10-3.13
- Node.js 20+
- Docker (for container builds)
- Git

### Build Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/langflow-ai/langflow.git
   cd langflow
   ```

2. **Install uv:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```

4. **Build frontend:**
   ```bash
   cd src/frontend
   npm install
   npm run build
   cd ../..
   ```

5. **Run Langflow:**
   ```bash
   uv run langflow run
   ```

### Docker Build on ppc64le

Build the Docker image natively on ppc64le:

```bash
docker build -t langflow:ppc64le -f docker/build_and_push.Dockerfile .
```

## Performance Considerations

### Expected Performance

- **CPU Performance:** IBM Power processors excel at parallel workloads and may outperform x86_64 in certain scenarios
- **Memory:** Power systems typically have excellent memory bandwidth
- **I/O:** Enterprise Power systems offer superior I/O capabilities

### Optimization Tips

1. **Use native builds:** Avoid emulation; use native ppc64le runners for CI/CD
2. **Leverage SMT:** IBM Power supports Simultaneous Multithreading (SMT) - configure appropriately
3. **Memory allocation:** Power systems benefit from larger memory allocations for Node.js builds
4. **Caching:** Use aggressive caching for Docker layers and Python packages

## CI/CD Integration

### GitHub Actions

To build for ppc64le in GitHub Actions, you need a self-hosted runner:

```yaml
jobs:
  build-ppc64le:
    runs-on: [self-hosted, linux, ppc64le]
    steps:
      - uses: actions/checkout@v6
      - name: Build Docker image
        run: |
          docker build -t langflow:ppc64le \
            -f docker/build_and_push.Dockerfile .
```

### Multi-Architecture Builds

The project uses Docker BuildKit for multi-architecture builds:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/ppc64le \
  -t langflowai/langflow:latest \
  -f docker/build_and_push.Dockerfile \
  --push .
```

## Troubleshooting

### Common Issues

#### 1. Missing Wheels for Native Dependencies

**Problem:** Package installation fails with "No matching distribution found"

**Solution:** 
- Check if the package is excluded on ppc64le (see platform markers in `pyproject.toml`)
- Try building from source with development headers installed
- Use alternative packages when available

#### 2. Node.js Architecture Detection

**Problem:** Node.js binary download fails

**Solution:**
- Verify Node.js has ppc64le binaries for your version
- The Dockerfile automatically handles architecture detection
- Use Node.js 20+ which has official ppc64le support

#### 3. Slow Docker Builds

**Problem:** Docker builds take very long on ppc64le

**Solution:**
- Use native ppc64le builders instead of emulation
- Enable BuildKit caching: `DOCKER_BUILDKIT=1`
- Increase memory allocation for Node.js: `NODE_OPTIONS="--max-old-space-size=8192"`

#### 4. Frontend Build Failures

**Problem:** npm build fails with memory errors

**Solution:**
```bash
# Increase Node.js memory
export NODE_OPTIONS="--max-old-space-size=12288"
npm run build
```

### Getting Help

- **GitHub Issues:** [langflow-ai/langflow/issues](https://github.com/langflow-ai/langflow/issues)
- **Discord:** [Langflow Community](https://discord.gg/EqksyE2EX9)
- **Documentation:** [docs.langflow.org](https://docs.langflow.org)

## Testing on ppc64le

### Unit Tests

Run unit tests on ppc64le:

```bash
uv run pytest src/backend/tests/unit \
  -m "not api_key_required" \
  -k "not playwright and not llama and not faiss"
```

### Integration Tests

Run integration tests:

```bash
uv run pytest src/backend/tests/integration \
  --ignore=tests/integration/test_browser_automation.py
```

### Docker Image Tests

Verify the Docker image works:

```bash
docker run --rm langflowai/langflow:latest langflow --help
docker run -p 7860:7860 langflowai/langflow:latest
```

## Contributing

We welcome contributions to improve ppc64le support! Areas where help is needed:

1. **Testing:** Test Langflow on various Power systems and workloads
2. **Performance:** Optimize builds and runtime performance for Power architecture
3. **Documentation:** Improve ppc64le-specific documentation
4. **Package Support:** Help add ppc64le wheels for missing packages

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

## Technical Details

### Architecture Detection

Langflow uses the following architecture detection in Dockerfiles:

```dockerfile
RUN ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "amd64" ]; then NODE_ARCH="x64"; \
       elif [ "$ARCH" = "arm64" ]; then NODE_ARCH="arm64"; \
       elif [ "$ARCH" = "ppc64el" ]; then NODE_ARCH="ppc64le"; \
       else NODE_ARCH="$ARCH"; fi
```

Note: Debian/Ubuntu use `ppc64el` while Node.js uses `ppc64le`.

### Platform Markers

Python packages use platform markers to exclude incompatible dependencies:

```toml
[project.optional-dependencies]
local = [
    "llama-cpp-python~=0.2.0; platform_machine != 'ppc64le'",
    "sentence-transformers>=2.3.1",
    "ctransformers>=0.2.10; platform_machine != 'ppc64le'"
]
```

### Build Process

1. **Base Image:** Uses `python:3.12-slim` with multi-arch support
2. **Node.js:** Downloads architecture-specific Node.js binaries
3. **Python Packages:** Uses IBM Power wheel repository when needed
4. **Frontend:** Builds with esbuild (has ppc64le support)
5. **Final Image:** Creates unified multi-arch manifest

## Roadmap

### Short-term (Current)
- ✅ Basic ppc64le support in Docker images
- ✅ Core functionality working on Power systems
- ✅ CI/CD pipeline updates
- ✅ Documentation

### Medium-term (Next 3-6 months)
- 🔄 Comprehensive testing on Power systems
- 🔄 Performance benchmarking and optimization
- 🔄 Community feedback and improvements
- 🔄 Additional package support

### Long-term (6+ months)
- 📋 Full feature parity with amd64/arm64
- 📋 Native ML library support (if upstream adds ppc64le)
- 📋 Performance optimizations specific to Power architecture
- 📋 Enterprise Power system integrations

## References

- [IBM Power Systems](https://www.ibm.com/power)
- [IBM Power Wheel Repository](https://wheels.developerfirst.ibm.com/ppc64le/linux)
- [Node.js ppc64le Support](https://nodejs.org/en/download/)
- [Docker Multi-Platform Builds](https://docs.docker.com/build/building/multi-platform/)
- [Python Platform Markers](https://peps.python.org/pep-0508/#environment-markers)

## License

Langflow is licensed under the MIT License. See [LICENSE](../LICENSE) for details.