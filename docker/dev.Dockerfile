FROM python:3.12-bookworm
ENV TZ=UTC

WORKDIR /app

RUN apt update -y
RUN apt install \
    build-essential \
    curl \
    npm \
    -y

COPY . /app

RUN pip install poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi

EXPOSE 7860
EXPOSE 3000

CMD ["./docker/dev.start.sh"]
