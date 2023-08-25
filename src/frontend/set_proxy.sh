#! /bin/bash
# Edit package.json to set proxy
backend_url=$BACKEND_URL
echo "Setting proxy to $backend_url"
# Load package.json file and edit proxy
packagejson=$(cat package.json)

packagejson=$(echo "$packagejson" | jq ".proxy = \"$backend_url\"")

echo "$packagejson" > package.json