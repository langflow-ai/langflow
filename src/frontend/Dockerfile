FROM node:20-alpine as frontend_build
ARG BACKEND_URL
WORKDIR /app
ENV NODE_OPTIONS=--max-old-space-size=4096

COPY ./package.json ./package-lock.json ./tsconfig.json ./vite.config.mts ./index.html ./tailwind.config.mjs ./postcss.config.js /app/
RUN npm install
COPY ./src /app/src
RUN npm run build

FROM nginx:alpine
ARG BACKEND_URL

# Copy built frontend files
COPY --from=frontend_build /app/build/ /usr/share/nginx/html

# Copy configuration files and scripts
COPY nginx.conf.template /usr/share/nginx/html/nginx.conf.template
COPY .env.example /usr/share/nginx/html/.env.example
COPY env.sh /usr/share/nginx/html/env.sh
COPY setup-nginx.sh /usr/share/nginx/html/setup-nginx.sh

# Make scripts executable
RUN chmod +x /usr/share/nginx/html/env.sh && \
    chmod +x /usr/share/nginx/html/setup-nginx.sh

# Set default environment variables
ENV BACKEND_URL=$BACKEND_URL
ENV FRONTEND_PORT=3000
ENV LANGFLOW_MAX_FILE_SIZE_UPLOAD=100

# Use the proper setup script
CMD ["/usr/share/nginx/html/setup-nginx.sh"]