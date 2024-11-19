FROM langflowai/langflow-nightly:latest

ENTRYPOINT ["python", "-m", "langflow", "run"]
