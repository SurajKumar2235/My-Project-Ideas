import logging
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv() -> bool:
        return False

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    MessageHandler,
    TypeHandler,
    filters,
    ContextTypes,
)

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
from bot.utils import send_reply

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


async def command_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Routes incoming commands to the appropriate handler.
    Works in both direct messages, groups, and channels.
    """
    # Handle both regular messages and channel posts
    message = update.message if update.message else update.channel_post
    
    if not message or not message.text:
        return
    
    # Command mapping for router
    command_handlers = {
        "start": start_command,
        "login": login_command,
        "logout": logout_command,
        "repo": repo_command,
        "plan": plan_command,
        "edit": edit_command,
        "push": push_command,
        "board": board_command,
        "create_task": create_task_command,
    }
    
    # Extract command and arguments from message text
    parts = message.text.split()
    command_text = parts[0]  # e.g., "/start"
    
    # Remove the leading slash to get the command name
    command = command_text.lstrip("/")
    
    # Extract arguments (excluding the command itself)
    args = parts[1:] if len(parts) > 1 else []
    
    # Set args in context for handlers that expect it
    context.args = args
    
    logger.info(f"Processing command /{command} with args: {args} (from {'channel' if update.channel_post else 'message'})")
    
    # Route to the appropriate handler
    if command in command_handlers:
        handler = command_handlers[command]
        logger.info(f"Routing command /{command} with args: {args}")
        await handler(update, context)
    else:
        logger.warning(f"Unknown command: /{command}")
        await send_reply(update, context, f"Unknown command: `/{command}`. Use `/start` for help.", parse_mode="Markdown")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/start`.
    """
    if not (update.message or update.channel_post):
        return
    
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
    await send_reply(update, context, welcome_text, parse_mode="Markdown")


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles channel posts with commands.
    Routes them to the command_router if they start with /.
    """
    if not update.channel_post or not update.channel_post.text:
        return
    
    # Only process if the message starts with /
    if update.channel_post.text.startswith("/"):
        logger.info(f"Detected channel post: {update.channel_post.text[:50]}")
        await command_router(update, context)


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler to catch exceptions and notify the chat.
    """
    logger.error("Exception while handling update:", exc_info=context.error)
    if isinstance(update, Update):
        try:
            await send_reply(
                update, context,
                f"❌ *An unexpected error occurred:* `{str(context.error)}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


def run_bot() -> None:
    """
    Main function to start the bot.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables. Exiting.")
        return

    logger.info("Building Telegram Application...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register error handler
    application.add_error_handler(global_error_handler)

    # Register command handlers using MessageHandler with regex filter
    # This works in both direct messages and groups
    application.add_handler(MessageHandler(filters.Regex(r"^/"), command_router))
    
    # Handle channel posts - they don't go through MessageHandler
    application.add_handler(TypeHandler(Update, handle_channel_post), group=0)

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
