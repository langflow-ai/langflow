ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Supported downstream contract: add a provider bundle while extending the
# published base application image, then return to the non-root runtime user.
USER root
COPY bundles-dist /tmp/bundles-dist
# Preserve the base image's package versions and install the release wheel when
# available, rather than selecting a newer bundle from the package index.
RUN uv pip list --python /app/.venv/bin/python --format freeze > /tmp/base-constraints.txt \
    && set -- /tmp/bundles-dist/lfx_openai-*.whl \
    && if [ ! -f "$1" ]; then set -- lfx-openai; fi \
    && [ "$#" -eq 1 ] \
    && uv pip install --python /app/.venv/bin/python \
        --prerelease=if-necessary-or-explicit \
        --constraint /tmp/base-constraints.txt \
        --find-links /tmp/bundles-dist "$@" \
    && uv pip check --python /app/.venv/bin/python \
    && rm -rf /tmp/bundles-dist /tmp/base-constraints.txt
USER user
