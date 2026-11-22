# The product's image: `fcon`, on Python 3.14 (ADR 0015). Built from the
# checkout: docker build . ; runs `fcon server` by default, `fcon db upgrade`
# when given `db upgrade`. Base images by tag and digest (Dependabot moves the
# digests, never off Python 3.14: ADR 0001).

FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv

# --- build: the virtual environment, in /app/.venv ---------------------------
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src

# The dependencies first, from the lock file and the four pyproject.toml
# files only: a change to the code reuses this layer.
COPY pyproject.toml uv.lock ./
COPY packages/fcon-sdk/pyproject.toml packages/fcon-sdk/README.md packages/fcon-sdk/
COPY packages/fcon-server/pyproject.toml packages/fcon-server/README.md packages/fcon-server/
COPY packages/fcon-cli/pyproject.toml packages/fcon-cli/README.md packages/fcon-cli/
RUN uv sync --locked --no-dev --no-editable --no-install-workspace

# Then the three packages, installed as built wheels.
COPY packages/fcon-sdk/src packages/fcon-sdk/src
COPY packages/fcon-server/src packages/fcon-server/src
COPY packages/fcon-cli/src packages/fcon-cli/src
RUN uv sync --locked --no-dev --no-editable

# --- the image: the environment only, run by a user who is not root ---------
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

LABEL org.opencontainers.image.title="Feather Connect" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/siraj-samsudeen/feather-connect"

RUN groupadd --system --gid 10001 fcon \
 && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin fcon

COPY --from=build /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    FCON_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER 10001:10001
EXPOSE 8080

# The port by the server's own rule: FCON_PORT, else PORT, else 8080.
HEALTHCHECK --interval=10s --start-period=30s --start-interval=1s --timeout=3s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; port = os.environ.get('FCON_PORT') or os.environ.get('PORT') or '8080'; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % port, timeout=2)"]

ENTRYPOINT ["fcon"]
CMD ["server"]
