FROM langflowai/langflow-backend

# Get the default username and store it in an environment variable
ARG DEFAULT_USER
RUN echo "DEFAULT_USER=$(whoami)" > /etc/default_user

# Ensure the following commands run as root
USER root

# Install sudo if not already available in the base image
RUN apt-get update && apt-get install -y sudo

# Set the entrypoint directly in the Dockerfile
ENTRYPOINT ["/bin/bash", "-c", "\
    source /etc/default_user; \
    MOUNT_POINT=\"${MOUNT_POINT:-/app/data}\"; \
    SIZE=\"${SIZE:-200M}\"; \
    TEMP_DIR=\"/tmp/data_backup\"; \
    mkdir -p \"$TEMP_DIR\"; \
    cp -r /app/data/* \"$TEMP_DIR/\"; \
    mkdir -p \"$MOUNT_POINT\"; \
    mount -t tmpfs -o size=$SIZE tmpfs \"$MOUNT_POINT\"; \
    cp -r \"$TEMP_DIR\"/* \"$MOUNT_POINT/\"; \
    rm -rf \"$TEMP_DIR\"; \
    chown -R $DEFAULT_USER:$DEFAULT_USER \"$MOUNT_POINT\"; \
    sudo -u $DEFAULT_USER python -m langflow run --host 0.0.0.0 --port 7860 --backend-only; \
"]
