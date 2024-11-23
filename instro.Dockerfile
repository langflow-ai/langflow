# Use a Python base image
FROM python:3.10-slim AS builder

# Install necessary packages
RUN apt-get update && apt-get install -y npm build-essential gcc && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy your code
COPY . /app

# Build the React frontend
WORKDIR /app/frontend
RUN npm ci && npm run build

# Copy built frontend to backend directory
RUN cp -r build /app/backend/langflow/frontend

# Go back to app directory and install Python dependencies
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

# Expose the port Langflow runs on
EXPOSE 7860

# Set environment variables
ENV LANGFLOW_LOG_LEVEL=ERROR
ENV LANGFLOW_SUPERUSER=instro
ENV LANGFLOW_SUPERUSER_PASSWORD=6p^m8jh5Z-Zjfu
ENV LANGFLOW_AUTO_LOGIN=false

# Start the Langflow application
ENTRYPOINT ["python", "-m", "langflow", "run", "--host", "0.0.0.0", "--port", "7860"]
