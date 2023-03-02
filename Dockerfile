FROM python:3.10-slim

WORKDIR /app

COPY --from=frontend_build /app/build/ /

EXPOSE 80

# CMD [ "langchain" ]
