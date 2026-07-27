ARG CORE_IMAGE
FROM ${CORE_IMAGE}

# Supported downstream contract: add a provider bundle while extending the
# published core application image, then return to the non-root runtime user.
USER root
COPY bundles-dist /tmp/bundles-dist
RUN uv pip install --python /app/.venv/bin/python \
        --prerelease=if-necessary-or-explicit \
        --find-links /tmp/bundles-dist lfx-openai \
    && uv pip check --python /app/.venv/bin/python \
    && rm -rf /tmp/bundles-dist
USER user
