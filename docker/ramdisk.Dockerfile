# Use the existing langflowai/langflow-backend image as the base
FROM langflowai/langflow-backend

# Install necessary tools
RUN apt-get update && apt-get install -y \
    mount \
    && rm -rf /var/lib/apt/lists/*

# Set the entrypoint directly in the Dockerfile
ENTRYPOINT ["/bin/bash", "-c", "\
    if [ \"$CREATE_RAMDISK\" = \"true\" ]; then \
        MOUNT_POINT=\"${MOUNT_POINT:-/app/data}\"; \
        SIZE=\"${SIZE:-200M}\"; \
        TEMP_DIR=\"/tmp/data_backup\"; \
        mkdir -p \"$TEMP_DIR\"; \
        cp -r /app/data/* \"$TEMP_DIR/\"; \
        mkdir -p \"$MOUNT_POINT\"; \
        mount -t tmpfs -o size=$SIZE tmpfs \"$MOUNT_POINT\"; \
        cp -r \"$TEMP_DIR/*\" \"$MOUNT_POINT/\"; \
        rm -rf \"$TEMP_DIR\"; \
    fi; \
    if [ $# -eq 0 ]; then \
        exec python -m langflow run --host 0.0.0.0 --port 7860 --backend-only; \
    else \
        exec \"$@\"; \
    fi \
"]
