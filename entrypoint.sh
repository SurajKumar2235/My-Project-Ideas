#!/bin/bash
set -e

# ==============================================================================
# LogicalFire Container Entrypoint
# Supports:
#   - web:  Runs FastAPI Web API server (can be scaled to N instances)
#   - bot:  Runs Telegram Bot (strictly 1 instance only!)
#   - both: Runs both Web API and Telegram Bot in a single container
# ==============================================================================

# Optionally run Aerich database migrations if requested
if [ "${RUN_MIGRATIONS,,}" = "true" ]; then
    echo "🔄 [Entrypoint] Running Aerich database migrations..."
    uv run aerich upgrade || echo "⚠️ [Entrypoint] Migration step skipped or database already initialized."
fi

# Determine target execution mode from $1 argument or $APP_ROLE / $MODE environment variables
MODE="${1:-${APP_ROLE:-${MODE:-both}}}"

case "$MODE" in
    web)
        echo "🌐 [Entrypoint] Starting FastAPI Web Server on port ${PORT:-8000} (Scalable Mode)..."
        exec uv run uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
        ;;

    bot)
        echo "🤖 [Entrypoint] Starting Telegram Bot (Single Instance Mode)..."
        exec uv run python bot_v2/main.py
        ;;

    both|all)
        echo "🚀 [Entrypoint] Starting both FastAPI Web Server (port ${PORT:-8000}) and Telegram Bot..."

        # Start Web API in background
        uv run uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
        API_PID=$!
        echo "   -> Web API server started with PID $API_PID"

        # Start Telegram Bot in background
        uv run python bot_v2/main.py &
        BOT_PID=$!
        echo "   -> Telegram Bot started with PID $BOT_PID"

        # Trap termination signals to ensure graceful shutdown of child processes
        cleanup() {
            echo "🛑 [Entrypoint] Termination signal received. Stopping child processes..."
            kill -TERM "$API_PID" "$BOT_PID" 2>/dev/null || true
            wait "$API_PID" "$BOT_PID" 2>/dev/null || true
            echo "✅ [Entrypoint] All processes stopped."
            exit 0
        }
        trap cleanup SIGTERM SIGINT

        # Wait for the first process to exit
        wait -n "$API_PID" "$BOT_PID"
        EXIT_STATUS=$?
        echo "⚠️ [Entrypoint] A core process exited with status $EXIT_STATUS. Shutting down container..."
        cleanup
        ;;

    *)
        echo "⚙️ [Entrypoint] Executing custom command: $@"
        exec "$@"
        ;;
esac

