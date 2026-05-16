FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DENO_INSTALL="/root/.deno" \
    BUN_INSTALL="/root/.bun" \
    PATH="/root/.deno/bin:/root/.bun/bin:${PATH}"

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    bash \
    git \
    unzip \
    ca-certificates && \

    # Install Deno
    curl -fsSL https://deno.land/install.sh | sh && \

    # Install Bun
    curl -fsSL https://bun.sh/install | bash && \

    # Upgrade pip
    pip install --upgrade pip setuptools wheel && \

    # Python requirements
    pip install --no-cache-dir -r requirements.txt && \

    # yt-dlp
    pip install --no-cache-dir yt-dlp && \

    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . .

# Cache Deno deps
RUN if [ -f deno.json ] || [ -f deno.jsonc ]; then \
      deno cache deno/*.ts 2>/dev/null || true ; \
    fi

# Cache Bun deps
RUN if [ -f package.json ]; then \
      bun install ; \
    fi

# Runtime folders
RUN mkdir -p downloads temp logs cache

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s \
CMD pgrep -f "python|deno|bun" || exit 1

CMD ["bash", "start"]