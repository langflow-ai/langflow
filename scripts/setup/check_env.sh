#!/bin/bash

# Detect if in a virtual environment (venv or virtualenv)
if [ -n "$VIRTUAL_ENV" ]; then
    exec "$@"
# Detect if in a conda environment
elif [ -n "$CONDA_DEFAULT_ENV" ]; then
    exec conda run -n "$CONDA_DEFAULT_ENV" "$@"
# Detect if in a pipenv environment
elif [ -f "Pipfile" ]; then
    exec pipenv run "$@"
# Detect if in a pyenv environment
elif [ -d ".pyenv" ]; then
    exec pyenv exec "$@"
# Detect if in a venv environment
elif [ -f "pyvenv.cfg" ]; then
    source bin/activate
    exec "$@"
else
    exec "$@"
fi
