#!/bin/bash
set -e
version=$1
package=$2
if [[ -z "$version" || -z "$package" ]]; then
    echo "Usage: $0 <version> <package>"
    echo "Packages: ragstack-ai-langflow-base, ragstack-ai-langflow."
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "Working directory not clean"
    exit 1
fi

tag="$package-$version"
directory=""
if [ "$package" == "ragstack-ai-langflow" ]; then
    directory="."
elif [ "$package" == "ragstack-ai-langflow-base" ]; then
    directory="src/backend/base"
else
    echo "Invalid package. Please choose from: ragstack-ai-langflow, ragstack-ai-langflow-base."
    exit 1
fi

cd $directory

git checkout ragstack-main
git pull
echo ":: Bumping version to $version for package $package"
poetry version $version
git commit -am "Release $package $version"
git tag $tag
git push origin ragstack-main
git push origin $tag
echo "done."