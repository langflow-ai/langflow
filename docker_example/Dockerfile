FROM langflowai/langflow:latest

# Switch to root so npm can write to node_modules
USER root

WORKDIR /app
COPY . /app

# Build frontend inside the image
RUN cd src/frontend && npm install && npm run build

# Copy built frontend into Langflow's serving directory
RUN cp -r src/frontend/build/* /app/.venv/lib/python3.12/site-packages/langflow/frontend/

# Switch back to the default non-root user for safety
USER 1000

CMD ["python", "-m", "langflow", "run", "--host", "0.0.0.0", "--port", "7860"]
