import logging
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from bot import db, locking
from bot.commands.plan import plan_command
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
        "I will help you capture project ideas, format them with Groq, "
        "push them as GitHub issues, and manage them on an interactive board.\n\n"
        "📋 *Available Commands:*\n"
        "💡 `/plan <idea>` - Draft and structure an idea, saving it locally as a file and in your drafts.\n"
        "🚀 `/push` - Push the latest draft to GitHub as a TODO issue.\n"
        "🛠 `/create_task [title]` - Create a single task issue manually, or parse all task items from your draft to bulk-create them.\n"
        "📊 `/board` - Display the Kanban board to claim or complete tasks.\n\n"
        "Get started by running `/plan <your project idea>`!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def stale_lock_cleanup_loop(application: Application):
    """
    Background loop that runs periodically to release stale claims.
    """
    logger.info("Stale lock cleanup loop started.")
    while True:
        try:
            # Check every 5 minutes (300 seconds)
            await asyncio.sleep(300)
            logger.info("Checking for expired locks...")
            expired_locks = await locking.expire_stale_locks()
            if expired_locks:
                logger.info(f"Automatically expired {len(expired_locks)} locks: {expired_locks}")
        except asyncio.CancelledError:
            logger.info("Stale lock cleanup loop cancelled.")
            break
        except Exception as e:
            logger.exception("Error in stale lock cleanup loop:")

async def post_init(application: Application) -> None:
    """
    Post-initialization hook to setup the DB and start background tasks.
    """
    logger.info("Initializing SQLite database...")
    db.init_db()
    
    # Run the stale lock cleanup loop in the background
    logger.info("Starting background tasks...")
    asyncio.create_task(stale_lock_cleanup_loop(application))

def run_bot() -> None:
    """
    Main function to start the bot.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables. Exiting.")
        return

    logger.info("Building Telegram Application...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("plan", plan_command))
    application.add_handler(CommandHandler("push", push_command))
    application.add_handler(CommandHandler("board", board_command))
    application.add_handler(CommandHandler("create_task", create_task_command))
    application.add_handler(CommandHandler("create-task", create_task_command))

    # Register callback query handlers
    application.add_handler(CallbackQueryHandler(board_callback_handler))
    application.add_handler(CallbackQueryHandler(push_callback_handler, pattern="^push_draft:"))

    logger.info("Starting polling loop. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
