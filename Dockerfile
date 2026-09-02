# ==============================================================================
# Production Dockerfile for LogicalFire Project Manager Bot & Web API
# Optimized for Amazon Container Registry (ECR), AWS ECS / Fargate, App Runner
# ==============================================================================

# Official uv image with Python 3.13 preinstalled on Debian Bookworm Slim
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Install system dependencies (curl and ca-certificates for health checks & TLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Configure container working directory
WORKDIR /app

# Configure Python and uv runtime environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000 \
    PLANS_DIR="/data"

# Step 1: Copy dependency lockfiles to leverage Docker layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Step 2: Copy remaining application code and complete project build
COPY . .
RUN uv sync --frozen --no-dev

# Step 3: Setup runtime data directory and permissions
RUN mkdir -p /data && \
    chmod +x /app/entrypoint.sh

# Security Best Practice: Create and run under a dedicated non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser && \
    chown -R appuser:appgroup /app /data

USER appuser

# Expose default HTTP port for Web API
EXPOSE 8000

# Container Healthcheck (Checks /health endpoint; passes if in bot-only worker mode)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8000}/health" || [ "$MODE" = "bot" ] || [ "$APP_ROLE" = "bot" ] || exit 1

# Launch container via flexible entrypoint (supports: 'web', 'bot', 'both')
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["both"]
