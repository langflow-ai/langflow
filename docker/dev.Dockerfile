FROM python:3.12-bookworm
ENV TZ=UTC
WORKDIR /app

RUN apt update -y
RUN apt install \
    build-essential \
    curl \
    npm \
    -y


RUN pip install poetry
RUN poetry config virtualenvs.create false
COPY . /app
RUN poetry install --no-interaction --no-ansi --extras deploy

EXPOSE 7860
EXPOSE 3000

CMD ["bash", "-c", "./docker/dev.start.sh"]
