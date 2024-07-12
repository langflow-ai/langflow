FROM langflowai/langflow:1.0-alpha

CMD ["python", "-m", "langflow", "run", "--host", "0.0.0.0", "--port", "7860"]
