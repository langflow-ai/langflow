FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set timezone
ENV TZ=UTC

# Set up work directory
WORKDIR /workspace

# Install additional dev dependencies
RUN apt-get update && apt-get install -y \
    zsh \
    curl \
    git \
    build-essential \
    npm \
    lsof \
    procps \
    vim \
    less \
    net-tools \
    sudo \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create the vscode user and group with the expected UID and GID (1000)
RUN groupadd -g 1000 langflow && \
    useradd -m -u 1000 -g 1000 -s /bin/zsh langflow && \
    echo "langflow ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set default shell to Zsh
SHELL ["/bin/zsh", "-c"]

RUN echo 'export PS1="%~ %# "' >> /home/langflow/.zshrc

# Set the default user
USER langflow
