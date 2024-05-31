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

remote_name=$(git remote -v  | grep push | grep datastax/ragstack-ai-langflow.git | awk '{print $1}' | head -n 1)
if [ -z "$remote_name" ]; then
    echo "Remote datastax/ragstack-ai-langflow.git not found"
    exit 1
fi
echo "Identified remote $remote_name"

if git rev-parse $tag >/dev/null 2>&1; then
    echo "Git tag $tag already exists"
    exit 1
fi

cd $directory
if [ "$package" == "ragstack-ai-langflow" ]; then
   base_version=$(poetry show ragstack-ai-langflow-base | grep -E "^ version" | awk '{print $3}')
   # for now we only check the exact version match
   if [ "$base_version" != "$version" ]; then
       echo "Version mismatch: ragstack-ai-langflow-base version $base_version != ragstack-ai-langflow version $version"
       exit 1
   fi
fi

git checkout ragstack-main
git pull $remote_name ragstack-main

echo ":: Bumping version to $version for package $package"
poetry version $version
git commit -am "Release $package $version"
git tag $tag
git push $remote_name ragstack-main
git push $remote_name $tag
echo "done."
