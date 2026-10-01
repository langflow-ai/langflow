# syntax=docker/dockerfile:1
FROM python:3.13.12-slim-bookworm@sha256:a58daefb915e1e03ad48f3ca4df8832065412c5c35cacb9d39f4229184de12b6
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ANONYMIZED_TELEMETRY=False HOME=/tmp OMP_NUM_THREADS=2
WORKDIR /helper
COPY tools/chroma_migration_helper/requirements.lock.txt /helper/requirements.lock.txt
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r /helper/requirements.lock.txt
COPY tools/chroma_migration_helper/export.py /helper/export.py
USER 10001:10001
ENTRYPOINT ["python", "-I", "/helper/export.py"]
