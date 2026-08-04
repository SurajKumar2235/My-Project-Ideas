import logging
import os
import asyncio

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv() -> bool:
        return False

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest

from bot.commands.auth import login_command, logout_command
from bot.commands.repo import repo_command, repo_callback_handler
from bot.commands.plan import (
    plan_command,
    edit_command,
    save_draft_callback_handler,
    plan_callback_handler,
    plan_feedback_message_handler,
)
from bot.commands.push import push_command, push_callback_handler
from bot.commands.board import board_command, board_callback_handler
from bot.commands.create_task import create_task_command

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/start`.
    """
    welcome_text = (
        "🤖 *Welcome to the Telegram → GitHub Project Manager Bot!*\n\n"
        "I will help you capture project ideas, format them with LLM, "
        "push them as GitHub issues, and manage them on an interactive board.\n\n"
        "🔑 *Authentication:*\n"
        "🔗 `/login` - Link your Telegram user to your GitHub account.\n"
        "🚪 `/logout` - Disassociate your GitHub account.\n"
        "📁 `/repo` - Select one of your write-accessible repositories.\n\n"
        "📋 *Project Commands:*\n"
        "💡 `/plan <idea>` - Draft and structure an idea, saving it locally as a file and in drafts.\n"
        "🚀 `/push` - Push the latest draft to GitHub as a TODO issue.\n"
        "🛠 `/create_task [title]` - Create a single task issue manually, or parse all task items from your draft to bulk-create them.\n"
        "📊 `/board` - Display the Kanban board to claim or complete tasks.\n\n"
        "To get started, please run `/login` to link your GitHub account!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


def run_bot() -> None:
    """
    Main function to start the bot.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables. Exiting.")
        return

    logger.info("Building Telegram Application...")
    # request = HTTPXRequest(http2=False)
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("login", login_command))
    application.add_handler(CommandHandler("logout", logout_command))
    application.add_handler(CommandHandler("repo", repo_command))
    application.add_handler(CommandHandler("plan", plan_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("push", push_command))
    application.add_handler(CommandHandler("board", board_command))
    application.add_handler(CommandHandler("create_task", create_task_command))

    # Register callback query handlers
    application.add_handler(CallbackQueryHandler(repo_callback_handler, pattern="^select_repo:"))
    application.add_handler(CallbackQueryHandler(push_callback_handler, pattern="^push_draft:"))
    application.add_handler(CallbackQueryHandler(save_draft_callback_handler, pattern="^save_draft:"))
    application.add_handler(CallbackQueryHandler(plan_callback_handler, pattern="^resend_ai:"))
    # Fallback to handle board callbacks
    application.add_handler(CallbackQueryHandler(board_callback_handler))

    # Register message handlers (for plan feedback)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, plan_feedback_message_handler))

    webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL")
    if webhook_url:
        webhook_port = int(os.environ.get("TELEGRAM_WEBHOOK_PORT", "8000"))
        webhook_listen = os.environ.get("TELEGRAM_WEBHOOK_LISTEN", "0.0.0.0")
        url_path = os.environ.get("TELEGRAM_WEBHOOK_URL_PATH", "")
        logger.info("Webhook server starting at %s:%s...", webhook_listen, webhook_port)
        application.run_webhook(
            listen=webhook_listen,
            port=webhook_port,
            url_path=url_path,
            webhook_url=f"{webhook_url.rstrip('/')}/{url_path.lstrip('/')}" if url_path else webhook_url,
        )
    else:
        logger.info("Starting polling loop. Press Ctrl+C to stop.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
