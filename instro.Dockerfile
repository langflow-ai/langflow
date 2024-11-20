# Use a Python base image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy your application's code to the working directory
COPY . /app

# Install the dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

# Expose the port Langflow runs on
EXPOSE 7860

# Set environment variables if needed
ENV LANGFLOW_LOG_LEVEL=ERROR
ENV LANGFLOW_SUPERUSER=instro
ENV LANGFLOW_SUPERUSER_PASSWORD=6p^m8jh5Z-Zjfu
ENV LANGFLOW_AUTO_LOGIN=false

# Start the Langflow application
ENTRYPOINT ["python", "-m", "langflow", "run", "--host", "0.0.0.0", "--port", "7860"]
