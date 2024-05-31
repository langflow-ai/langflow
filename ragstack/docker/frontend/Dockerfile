FROM python:3.11-slim as builder
ARG RAGSTACK_AI_LANGFLOW_VERSION
RUN pip install --no-cache-dir ragstack-ai-langflow-base==$RAGSTACK_AI_LANGFLOW_VERSION --no-deps
RUN pip show ragstack-ai-langflow-base | grep Location | cut -d ' ' -f 2 | xargs -I {} cp -r {}/langflow/frontend /tmp/frontend


FROM nginxinc/nginx-unprivileged:stable-bookworm-perl
COPY --from=builder --chown=nginx /tmp/frontend /usr/share/nginx/html
COPY --chown=nginx /nginx.conf /etc/nginx/conf.d/default.conf
COPY --chown=nginx start-nginx.sh /start-nginx.sh
RUN chmod +x /start-nginx.sh
CMD ["/start-nginx.sh"]
