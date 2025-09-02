#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DRY_RUN=false

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_dry_run() {
    echo -e "${BLUE}[DRY RUN]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [VERSION]"
    echo ""
    echo "Options:"
    echo "  --dry-run    Run the script without making actual changes"
    echo "  --help       Show this help message"
    echo ""
    echo "Arguments:"
    echo "  VERSION      The new version to release (e.g., 0.1.0)"
    echo ""
    echo "Examples:"
    echo "  $0 0.1.0               # Release version 0.1.0"
    echo "  $0 --dry-run 0.1.0     # Dry run for version 0.1.0"
    echo "  $0 --dry-run           # Dry run with interactive version prompt"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            if [ -z "$NEW_VERSION" ]; then
                NEW_VERSION=$1
            fi
            shift
            ;;
    esac
done

# Check if we're in the right directory
if [ ! -f "src/lfx/pyproject.toml" ]; then
    print_error "This script must be run from the root of the langflow repository"
    exit 1
fi

# Get current version
CURRENT_VERSION=$(grep '^version = ' src/lfx/pyproject.toml | cut -d'"' -f2)
print_info "Current LFX version: $CURRENT_VERSION"

if [ "$DRY_RUN" = true ]; then
    print_dry_run "Running in dry run mode - no changes will be made"
fi

# Check for uncommitted changes (skip in dry run)
if [ "$DRY_RUN" = false ]; then
    if ! git diff-index --quiet HEAD --; then
        print_warning "You have uncommitted changes. Please commit or stash them before releasing."
        exit 1
    fi
else
    if ! git diff-index --quiet HEAD --; then
        print_warning "Uncommitted changes detected (ignored in dry run mode)"
    fi
fi

# Get new version from argument or prompt
if [ -z "$NEW_VERSION" ]; then
    echo -n "Enter new version (current: $CURRENT_VERSION): "
    read NEW_VERSION
fi

# Validate version format
if ! [[ $NEW_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$ ]]; then
    print_error "Invalid version format. Use semantic versioning (e.g., 0.1.0 or 0.1.0-alpha)"
    exit 1
fi

print_info "Preparing to release LFX version $NEW_VERSION"

# Update version in pyproject.toml
if [ "$DRY_RUN" = true ]; then
    print_dry_run "Would update version in pyproject.toml to $NEW_VERSION"
else
    print_info "Updating version in pyproject.toml..."
    sed -i.bak "s/^version = \".*\"/version = \"$NEW_VERSION\"/" src/lfx/pyproject.toml
    rm src/lfx/pyproject.toml.bak
fi

# Update version in Dockerfiles if they have ARG LFX_VERSION
if grep -q "ARG LFX_VERSION" src/lfx/docker/Dockerfile 2>/dev/null; then
    if [ "$DRY_RUN" = true ]; then
        print_dry_run "Would update version in Dockerfiles to $NEW_VERSION"
    else
        print_info "Updating version in Dockerfiles..."
        sed -i.bak "s/ARG LFX_VERSION=.*/ARG LFX_VERSION=$NEW_VERSION/" src/lfx/docker/Dockerfile*
        rm src/lfx/docker/Dockerfile*.bak
    fi
fi

# Run tests
print_info "Running tests..."
cd src/lfx
if ! make test; then
    print_error "Tests failed!"
    if [ "$DRY_RUN" = false ]; then
        print_info "Rolling back changes..."
        git checkout -- .
    fi
    exit 1
fi
cd ../..

# Build package to verify
print_info "Building package..."
cd src/lfx
if ! uv build; then
    print_error "Build failed!"
    if [ "$DRY_RUN" = false ]; then
        print_info "Rolling back changes..."
        cd ../..
        git checkout -- .
    fi
    exit 1
fi
cd ../..
if [ "$DRY_RUN" = true ]; then
    print_dry_run "Skipping cleanup of build artifacts in dry run mode"
else
    # Clean up build artifacts
    rm -rf src/lfx/dist/
fi

# Create git commit
if [ "$DRY_RUN" = true ]; then
    print_dry_run "Would create git commit: 'chore(lfx): bump version to $NEW_VERSION'"
else
    print_info "Creating git commit..."
    git add src/lfx/pyproject.toml src/lfx/docker/Dockerfile* 2>/dev/null || true
    git commit -m "chore(lfx): bump version to $NEW_VERSION

- Update version in pyproject.toml
- Prepare for PyPI and Docker release"
fi

# Create git tag
TAG_NAME="lfx-v$NEW_VERSION"
if [ "$DRY_RUN" = true ]; then
    print_dry_run "Would create git tag: $TAG_NAME"
else
    print_info "Creating git tag: $TAG_NAME"
    git tag -a "$TAG_NAME" -m "LFX Release $NEW_VERSION"
fi

if [ "$DRY_RUN" = true ]; then
    print_info "✅ Dry run complete!"
    echo ""
    echo "Dry run performed:"
    echo "✅ Validated version format"
    echo "✅ Ran tests successfully"
    echo "✅ Built package successfully"
    echo ""
    echo "What would happen in a real run:"
    echo "1. Update version in pyproject.toml to $NEW_VERSION"
    echo "2. Update version in Dockerfiles (if applicable)"
    echo "3. Create git commit with message: 'chore(lfx): bump version to $NEW_VERSION'"
    echo "4. Create git tag: $TAG_NAME"
    echo ""
    echo "To perform the actual release, run without --dry-run:"
    echo "   $0 $NEW_VERSION"
else
    print_info "✅ Release preparation complete!"
    echo ""
    echo "Next steps:"
    echo "1. Push the commit and tag:"
    echo "   git push origin HEAD"
    echo "   git push origin $TAG_NAME"
    echo ""
    echo "2. Go to GitHub Actions and run the 'LFX Release' workflow:"
    echo "   https://github.com/langflow-ai/langflow/actions/workflows/release-lfx.yml"
    echo ""
    echo "3. Enter version: $NEW_VERSION"
    echo ""
    echo "4. Select options:"
    echo "   - Publish to PyPI: Yes"
    echo "   - Build Docker images: Yes"
    echo "   - Create GitHub release: Yes"
    echo ""
    echo "The workflow will:"
    echo "- Run tests on all Python versions"
    echo "- Build and publish to PyPI"
    echo "- Build and push Docker images (standard and alpine)"
    echo "- Create a GitHub release with artifacts"
fi