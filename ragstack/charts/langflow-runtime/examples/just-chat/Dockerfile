FROM ghcr.io/datastax/ragstack-ai-langflow-backend:0.0.8
RUN mkdir /app/flows
COPY ./*json /app/flows/.
ENV LANGFLOW_LOAD_FLOWS_PATH=/app/flows
