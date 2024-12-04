#!/bin/zsh

# Detect and use appropriate Python interpreter from virtual environments
if [ -n "$VIRTUAL_ENV" ]; then
    PYTHON_EXEC=python
elif [ -n "$CONDA_DEFAULT_ENV" ]; then
    # PYTHON_EXEC=("conda" "run" "-n" "$CONDA_DEFAULT_ENV" "python")
    PYTHON_EXEC=("conda run -n ${CONDA_DEFAULT_ENV} python")
elif [ -f "Pipfile" ]; then
    PYTHON_EXEC=("pipenv run python")
elif [ -d ".pyenv" ]; then
    PYTHON_EXEC=("pyenv exec python")
else
    PYTHON_EXEC=python
fi

# Check if Python version is compatible
REQUIRED_VERSION=$1
PYTHON_INSTALLED=$($PYTHON_EXEC -c "import sys; print(sys.version.split()[0])")


echo "Detected Python version: $PYTHON_INSTALLED"

$PYTHON_EXEC -c "
import sys
from distutils.version import LooseVersion

required_version = '$REQUIRED_VERSION'
python_installed = '$PYTHON_INSTALLED'

min_version, max_version = required_version.replace('>=', '').replace('<', '').split(',')
if not (LooseVersion(min_version) <= LooseVersion(python_installed) < LooseVersion(max_version)):
    sys.exit(f'Error: Python version {python_installed} is not compatible with required version {required_version}.')
" || exit 1
