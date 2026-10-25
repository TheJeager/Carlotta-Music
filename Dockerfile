FROM python:3.13-slim-bookworm

ARG DENO_VERSION=2.5.6

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DENO_INSTALL=/root/.deno \
    PATH=/root/.deno/bin:${PATH}

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl ca-certificates procps && \
    curl -fsSL https://deno.land/install.sh -o /tmp/deno-install.sh && \
    DENO_VERSION=${DENO_VERSION} sh /tmp/deno-install.sh && \
    rm -f /tmp/deno-install.sh && \
    pip install --no-cache-dir pip==25.3 setuptools==80.9.0 wheel==0.45.1 && \
    pip install --no-cache-dir -r requirements.txt && \
    deno --version && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . .

RUN mkdir -p downloads temp logs cache carlotta/cookies

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD pgrep -f "python.*-m carlotta" >/dev/null || exit 1

CMD ["python", "-m", "carlotta"]
