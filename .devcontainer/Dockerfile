# The eval image: what a headless agent needs to run an eval case, and nothing else.
# Claude Code (pinned), uv with Python 3.15, Node with Backlog.md, git, and bubblewrap and
# socat for Claude Code's Bash sandbox. No credentials are baked in: a run passes
# CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`) or ANTHROPIC_API_KEY at `docker run`.
#
# Multi-arch: every base image here is published for linux/amd64 and linux/arm64, and no
# step downloads an architecture-specific file by name.
#
#   docker build -t asdlc-evals:local .devcontainer
#
# Behind a proxy that re-signs TLS, pass its CA for the build only (it is not kept in the image):
#   docker build --network host --secret id=extra_ca,src=<ca.pem> -t asdlc-evals:local .devcontainer

ARG UV_VERSION=0.13.4
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM node:22-trixie-slim

ARG CLAUDE_CODE_VERSION=2.1.309
ARG BACKLOG_VERSION=1.55.2
ARG PYTHON_VERSION=3.15

ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_PROGRESS=1 \
    DISABLE_AUTOUPDATER=1

COPY --from=uv /uv /uvx /usr/local/bin/

# The CA secret, when given, is trusted for the duration of each step that downloads.
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca NODE_EXTRA_CA_CERTS=/run/secrets/extra_ca; fi; \
    apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git bubblewrap socat ripgrep python3 procps \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/extra_ca; fi; \
    npm install --global --no-fund --no-audit "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" "backlog.md@${BACKLOG_VERSION}" \
    && npm cache clean --force \
    && claude --version | grep -q "^${CLAUDE_CODE_VERSION} "

RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    UV_PYTHON_DOWNLOADS=automatic uv python install "${PYTHON_VERSION}" \
    && chmod -R a+rX /opt/uv \
    && uv run --python "${PYTHON_VERSION}" python -c "import sys; assert sys.version_info >= (3, 15)"

# Agents run as the invoking user's uid (docker run --user), with HOME in the mounted fixture.
RUN git config --system init.defaultBranch main && git config --system commit.gpgsign false

WORKDIR /workspace
CMD ["claude", "--version"]
