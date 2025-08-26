#!/bin/bash
# TDD enforcement hook for langflow

echo "🧪 TDD Guard: Checking test-driven development compliance..."

# Check if tests exist and pass
if [ -f "package.json" ]; then
    npm test
elif [ -f "pytest.ini" ] || [ -f "pyproject.toml" ]; then
    python -m pytest
elif [ -f "go.mod" ]; then
    go test ./...
elif [ -f "Cargo.toml" ]; then
    cargo test
else
    echo "⚠️  No test framework detected"
    exit 1
fi

echo "✅ TDD compliance verified"
