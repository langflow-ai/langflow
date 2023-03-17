FROM python:3.11-slim

RUN apt-get update && apt-get install gcc -y
RUN pip install langflow>=0.0.33

EXPOSE 7860
CMD ["langflow", "--host", "0.0.0.0"]