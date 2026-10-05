# syntax=docker/dockerfile:1
FROM python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ANONYMIZED_TELEMETRY=False HOME=/tmp OMP_NUM_THREADS=2
WORKDIR /helper
COPY tools/chroma_migration_helper/requirements.lock.txt /helper/requirements.lock.txt
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r /helper/requirements.lock.txt \
    && python -m pip uninstall --yes pip
COPY tools/chroma_migration_helper/export.py /helper/export.py
USER 10001:10001
ENTRYPOINT ["python", "-I", "/helper/export.py"]
