FROM python:3.12.3-slim

# Definir variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    LANGFLOW_HOST=0.0.0.0 \
    LANGFLOW_PORT=7860

# Instalar dependências necessárias
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
    build-essential \
    git \
    npm \
    gcc \
    libpq-dev \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv
RUN pip install uv

# Configurar diretório de trabalho
WORKDIR /app

# Copiar arquivos de projeto necessários
COPY pyproject.toml uv.lock README.md ./
COPY src ./src/

# Compilar o frontend
WORKDIR /app/src/frontend
RUN npm ci && \
    npm run build && \
    mkdir -p /app/src/backend/langflow/frontend && \
    cp -r build /app/src/backend/langflow/frontend

# Voltar ao diretório principal
WORKDIR /app

# Instalar dependências Python com uv (sem ambiente virtual)
RUN uv pip install --system -e ".[postgresql]" && \
    pip install psycopg2-binary psycopg "psycopg[binary,pool]" && \
    pip list | grep psycopg

# Configurar usuário não-root para segurança
RUN useradd -m user -u 1000
USER user

# Comando para iniciar a aplicação
CMD ["langflow", "run"]
