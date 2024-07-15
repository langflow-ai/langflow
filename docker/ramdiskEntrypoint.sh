#!/bin/bash

# Check if CREATE_RAMDISK environment variable is set to true
if [ "$CREATE_RAMDISK" = "true" ]; then
    # Use the MOUNT_POINT environment variable or default to /mnt/ramdisk
    MOUNT_POINT="${RAMDISK_MOUNT_POINT:-/mnt/ramdisk}"
    
    # Use the SIZE environment variable or default to 100M
    SIZE="${RAMDISK_SIZE:-200M}"
    
    mkdir -p "$MOUNT_POINT"
    mount -t tmpfs -o size=$SIZE tmpfs "$MOUNT_POINT"
fi

# Execute the original entrypoint command or the command passed to docker run
if [ $# -eq 0 ]; then
    exec python -m langflow run --host 0.0.0.0 --port 7860 --backend-only
else
    exec "$@"
fi
