FROM langflowai/langflow:latest

ENV LANGFLOW_AUTO_LOGIN=false

ENTRYPOINT ["python", "-m", "langflow", "run"]
