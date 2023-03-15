FROM python:3.11-slim

WORKDIR /app
COPY ./ /app
RUN pip install langflow

EXPOSE 5003
CMD ["langflow", "--host", "0.0.0.0"]