# Use the existing langflowai/langflow-backend image as the base
FROM langflowai/langflow-backend:1.0.9

# Add the entrypoint script to the image
COPY entrypoint.sh /usr/local/bin/ramdiskEntrypoint.sh
RUN chmod +x /usr/local/bin/ramdiskEntrypoint.sh

# Set the new entrypoint
ENTRYPOINT ["/usr/local/bin/ramdiskEntrypoint.sh"]
