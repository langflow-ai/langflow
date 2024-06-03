#!/bin/bash
set -e
RAGSTACK_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

cd $RAGSTACK_DIR
if command -v poetry &> /dev/null
then
    version=$(poetry version | awk '{print $2}')
else
    pyproject="$RAGSTACK_DIR/../pyproject.toml"
    echo "pyproject file $pyproject"
    if [[ -f "$pyproject" ]]; then
        version=$(grep "^version" $pyproject | awk -F'=' '{gsub(/ /,"",$2); print $2}' | tr -d '"')
        if [[ -n "$version" ]]; then
            echo "Poetry is not installed. Version from pyproject.toml: $version"
        else
            echo "Version not found in $pyproject."
            exit 1
        fi
    else
        echo "pyproject.toml file $pyproject not found."
        exit 1
    fi
fi

echo "build docker image version $version ..."

cd $RAGSTACK_DIR/docker/backend
echo "Building backend image"
docker build --build-arg VERSION=${version} -t ragstack-ai-langflow-backend:latest -f Dockerfile ../../..
echo "Done ragstack-ai-langflow-backend:latest "

cd $RAGSTACK_DIR/docker/backend-ep
docker build --build-arg VERSION=${version} -t ragstack-ai-langflow-backend-ep:latest -f Dockerfile ../../..
echo "Done ragstack-ai-langflow-backend-ep:latest "

