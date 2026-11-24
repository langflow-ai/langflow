#!/bin/sh

set -eu

base_version=${1:?"usage: rewrite_langflow_base_constraint.sh BASE_VERSION [PYPROJECT_PATH]"}
pyproject_path=${2:-/app/pyproject.toml}
base_major=${base_version%%.*}
base_remainder=${base_version#*.}
base_minor=${base_remainder%%.*}
base_upper_bound="${base_major}.$((base_minor + 1)).dev0"

sed -i -E \
    "s|\"langflow-base(\\[[^]]+\\])?[^\";]*\"|\"langflow-base\\1>=${base_version},<${base_upper_bound}\"|g" \
    "$pyproject_path"
