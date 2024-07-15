# Use the existing langflowai/langflow-backend image as the base
FROM langflowai/langflow-backend:1.0.9

# Set the entrypoint directly in the Dockerfile
ENTRYPOINT ["/bin/bash", "-c", "\
    if [ \"$CREATE_RAMDISK\" = \"true\" ]; then \
        MOUNT_POINT=\"${MOUNT_POINT:-/app/data}\"; \
        SIZE=\"${SIZE:-200M}\"; \
        mkdir -p \"$MOUNT_POINT\"; \
        mount -t tmpfs -o size=$SIZE tmpfs \"$MOUNT_POINT\"; \
    fi; \
    if [ $# -eq 0 ]; then \
        exec python -m langflow run --host 0.0.0.0 --port 7860 --backend-only; \
    else \
        exec \"$@\"; \
    fi \
"]


