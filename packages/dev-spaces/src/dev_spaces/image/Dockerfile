# dev-spaces base image: shared tooling for every container.
# Project dependencies are installed per container after cloning, not here.
FROM debian:trixie-slim

ARG DEV_SPACES_VERSION=0.0.0
LABEL dev-spaces.version="${DEV_SPACES_VERSION}"

# System packages. gh comes from GitHub's apt repo for a current version.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git less locales openssh-client procps sudo vim zsh \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8

# Non-root user with passwordless sudo: the container is the sandbox,
# so agents may install system packages inside it.
RUN useradd --create-home --shell /usr/bin/zsh dev \
    && echo "dev ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev \
    && chmod 0440 /etc/sudoers.d/dev

USER dev
WORKDIR /home/dev
ENV PATH="/home/dev/.local/bin:/home/dev/.pixi/bin:${PATH}"

# Python tooling and Claude Code, installed per user
RUN curl -fsSL https://pixi.sh/install.sh | PIXI_NO_PATH_UPDATE=1 bash \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh \
    && curl -fsSL https://claude.ai/install.sh | bash

RUN mkdir -p /home/dev/code

# Keep the container alive; work happens through `docker exec`
CMD ["sleep", "infinity"]
