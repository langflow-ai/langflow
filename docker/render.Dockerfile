FROM langflowai/langflow-nightly:v1.1.0.dev4

ENTRYPOINT ["python", "-m", "langflow", "run"]
