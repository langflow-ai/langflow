#!/bin/sh

set -eu

lxml_python=/app/.venv/bin/python
lxml_version="$("$lxml_python" -c 'from importlib.metadata import version; print(version("lxml"))')"

# Rebuild only lxml without cached wheels or an existing installation shortcut.
uv pip install --python "$lxml_python" \
    --no-cache --no-deps --force-reinstall --no-binary lxml \
    "lxml==$lxml_version"
