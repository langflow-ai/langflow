FROM --platform=linux/amd64 registry.access.redhat.com/ubi10/python-314-minimal
USER root
WORKDIR /app

# Install Poetry
RUN microdnf install -y python3.14-devel tar xz gcc gcc-c++ make curl postgresql-devel \
    && microdnf clean all
RUN curl -sSL https://install.python-poetry.org | python3 -
# # Add Poetry to PATH
ENV PATH="${PATH}:/root/.local/bin"
# # Copy the pyproject.toml and poetry.lock files
COPY poetry.lock pyproject.toml ./
# Copy the rest of the application codes
COPY ./ ./

# Install dependencies
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

RUN poetry add botocore
RUN poetry add pymysql

CMD ["sh", "./container-cmd-cdk.sh"]
