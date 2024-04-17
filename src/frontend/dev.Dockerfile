#baseline
FROM node:21-bookworm-slim AS base
RUN mkdir -p /home/node/app
RUN chown -R node:node /home/node && chmod -R 770 /home/node
RUN apt-get update && apt-get install -y jq
WORKDIR /home/node/app

# client build
FROM base AS builder-client
ARG BACKEND_URL
ENV BACKEND_URL $BACKEND_URL
RUN echo "BACKEND_URL: $BACKEND_URL"

WORKDIR /home/node/app
COPY --chown=node:node . ./

COPY ./set_proxy.sh .
RUN chmod +x set_proxy.sh && \
    cat set_proxy.sh | tr -d '\r' > set_proxy_unix.sh && \
    chmod +x set_proxy_unix.sh && \
    ./set_proxy_unix.sh

USER node

RUN npm install --loglevel warn
CMD ["npm", "run", "dev:docker"]