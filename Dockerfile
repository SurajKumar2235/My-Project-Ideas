# Use a builder stage with uv
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Copy configuration files and sync dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application files and sync project
COPY . .
RUN uv sync --frozen --no-dev

# Final runtime image
FROM docker.io/library/python:3.13-slim
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"

# Create data directory for persistent project plan storage
RUN mkdir -p /data
ENV PLANS_DIR="/data"

# Start the application
CMD ["python", "main.py"]
