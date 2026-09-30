Release workflows download the wheels built for PyPI into this directory before
building Docker images. Keeping the directory in the repository lets ordinary
nightly and local Docker builds use the same Dockerfiles without supplying
release artifacts.
