# Use the official uv bookworm image which has both python and uv preinstalled
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1

# Copy lock files and sync dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy project files and build
COPY . .
RUN uv sync --frozen --no-dev

# Create data directory for local project plan storage if needed
RUN mkdir -p /data
ENV PLANS_DIR="/data"

# Expose default port for web
EXPOSE 8000

# Defaults to running the web server using uv run
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
