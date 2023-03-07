FROM logspace/frontend_build as frontend_build

FROM nginx
COPY --from=frontend_build /app/build/ /usr/share/nginx/html
COPY /nginx.conf /etc/nginx/conf.d/default.conf