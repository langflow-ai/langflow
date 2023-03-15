FROM python:3.11-slim

WORKDIR /app
COPY ./ /app
RUN pip install langflow>=0.0.33

EXPOSE 5003
CMD ["langflow", "--host", "0.0.0.0"]