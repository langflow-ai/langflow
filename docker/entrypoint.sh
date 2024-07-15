#!/bin/bash

# Install gosu if not already installed
if ! command -v gosu &> /dev/null; then
    apt-get update && \
    apt-get install -y gosu && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
fi

# Use the MOUNT_POINT environment variable or default to /app/data
MOUNT_POINT="${RAMDISK_MOUNT_POINT:-/app/data}"

# Use the SIZE environment variable or default to 200M
SIZE="${RAMDISK_SIZE:-200M}"

mkdir -p "$MOUNT_POINT"
mount -t tmpfs -o size=$SIZE tmpfs "$MOUNT_POINT"

# Change ownership and group to uid and gid 1000
chown 1000:1000 "$MOUNT_POINT"

# Execute the original entrypoint command or the command passed to docker run as uid 1000
if [ $# -eq 0 ]; then
    exec gosu 1000:1000 python -m langflow run --host 0.0.0.0 --port 7860
else
    exec gosu 1000:1000 "$@"
fi
