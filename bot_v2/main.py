import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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

from bot_v2.commands.auth import login_command, logout_command
from bot_v2.commands.repo import repo_command, repo_callback_handler
from bot_v2.commands.plan import (
    plan_command,
    edit_command,
    save_draft_callback_handler,
    plan_callback_handler,
    plan_feedback_message_handler,
)
from bot_v2.commands.push import push_command, push_callback_handler
from bot_v2.commands.board import board_command, board_callback_handler
from bot_v2.commands.create_task import (
    create_task_command,
    create_task_callback_handler,
    task_prompt_message_handler,
)
from bot_v2.commands.admin import (
    admin_users_command,
    set_role_command,
    set_command_permissions_command,
)
from bot_v2.utils import send_reply
from bot_v2 import api_client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


async def combined_text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles non-command text messages for interactive prompts (e.g. task details entry, plan refinement).
    """
    if await task_prompt_message_handler(update, context):
        return
    await plan_feedback_message_handler(update, context)


async def command_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Central Command Router with Permission Verification.
    Routes incoming commands to appropriate handlers, enforcing role and per-user command permissions.
    """
    message = update.message if update.message else update.channel_post
    if not message or not message.text:
        return

    # Extract command and arguments
    parts = message.text.split()
    command_text = parts[0]
    command = command_text.lstrip("/").split("@")[0].lower()  # handle bot mentions like /start@bot
    args = parts[1:] if len(parts) > 1 else []
    context.args = args

    user_id = update.effective_user.id if update.effective_user else None

    # Public commands that anyone can run without permission checks
    public_commands = {"start", "help", "login", "logout"}

    # Admin commands
    admin_commands = {"users", "admin_users", "set_role", "set_command"}

    # Mapping of all supported commands
    command_handlers = {
        "start": start_command,
        "help": start_command,
        "login": login_command,
        "logout": logout_command,
        "repo": repo_command,
        "plan": plan_command,
        "edit": edit_command,
        "push": push_command,
        "board": board_command,
        "create_task": create_task_command,
        "users": admin_users_command,
        "admin_users": admin_users_command,
        "set_role": set_role_command,
        "set_command": set_command_permissions_command,
    }

    if command not in command_handlers:
        logger.warning(f"Unknown command: /{command}")
        await send_reply(update, context, f"❌ *Unknown Command:* `/{command}`. Run `/start` for help.", parse_mode="Markdown")
        return

    # Perform Permission Check if user is present and command is restricted
    if user_id and command not in public_commands:
        try:
            auth_info = await api_client.identify_user(user_id)
            is_admin = auth_info.get("is_admin", False)
            user_data = auth_info.get("user") or {}
            role = user_data.get("role", "user")
            allowed_cmds = user_data.get("allowed_commands")

            # Check 1: Admin commands require admin/superadmin access
            if command in admin_commands:
                if not (is_admin or role in ("admin", "superadmin")):
                    await send_reply(
                        update, context,
                        f"⛔️ *Access Denied:* Admin privileges are required to run `/{command}`.",
                        parse_mode="Markdown"
                    )
                    return

            # Check 2: Standard user command permission rules
            elif not (is_admin or role in ("admin", "superadmin")):
                if allowed_cmds is not None:
                    # Specific allowed commands list is enforced
                    if command not in allowed_cmds and "*" not in allowed_cmds:
                        await send_reply(
                            update, context,
                            f"⛔️ *Permission Denied:* You do not have permission to execute `/{command}`.\n"
                            "Contact an administrator to grant permission using `/set_command`.",
                            parse_mode="Markdown"
                        )
                        return

        except Exception as e:
            logger.error(f"Error checking user permissions for /{command}: {e}")

    logger.info(f"Routing command /{command} with args: {args} (User: {user_id})")
    handler = command_handlers[command]
    await handler(update, context)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/start` and `/help`.
    """
    if not (update.message or update.channel_post):
        return

    welcome_text = (
        "🤖 *Welcome to the Redesigned Telegram Project Manager Bot (V2)!*\n\n"
        "I will help you capture project ideas, format them with LLM reasoning, "
        "push them as GitHub issues, and manage them on an interactive Kanban board.\n\n"
        "🔑 *Authentication & Repos:*\n"
        "• `/login` - Link your Telegram account to GitHub.\n"
        "• `/logout` - Disassociate your GitHub account.\n"
        "• `/repo` - Select one of your write-accessible GitHub repositories.\n\n"
        "📋 *Project & Planning:*\n"
        "• `/plan <idea>` - Draft a project specification with AI reasoning.\n"
        "• `/edit <feedback>` - Refine your project plan draft with AI.\n"
        "• `/push` - Push the active draft to GitHub as a TODO issue.\n"
        "• `/create_task [title]` - Create a single task or bulk-parse draft task checkboxes.\n"
        "• `/board` - Interactive Kanban board (Claim, Release, Complete tasks).\n\n"
        "🛡 *Administrator Commands:*\n"
        "• `/users` - List all registered bot users, roles, and permissions.\n"
        "• `/set_role <user_id> <role>` - Update user role (`user`, `admin`, `superadmin`).\n"
        "• `/set_command <user_id> <cmds>` - Set allowed commands per user (`repo,plan`, `all`, `none`).\n\n"
        "Run `/login` to get started!"
    )
    await send_reply(update, context, welcome_text, parse_mode="Markdown")


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles channel posts starting with /.
    """
    if not update.channel_post or not update.channel_post.text:
        return

    if update.channel_post.text.startswith("/"):
        logger.info(f"Detected channel post command: {update.channel_post.text[:50]}")
        await command_router(update, context)


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler.
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
            logger.error(f"Failed to send error message: {e}")


async def debug_callback_query_logger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        logger.info(f"📥 CallbackQuery received: data='{update.callback_query.data}' from user={update.callback_query.from_user.id}")


def run_bot() -> None:
    """
    Starts Bot V2 application.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables. Exiting.")
        return

    logger.info("Building Telegram Application (Bot V2)...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Error handler
    application.add_error_handler(global_error_handler)

    # 1. Callback Query Handlers
    application.add_handler(CallbackQueryHandler(repo_callback_handler, pattern="^select_repo:"))
    application.add_handler(CallbackQueryHandler(push_callback_handler, pattern="^push_draft:"))
    application.add_handler(CallbackQueryHandler(save_draft_callback_handler, pattern="^save_draft:"))
    application.add_handler(CallbackQueryHandler(plan_callback_handler, pattern="^resend_ai:"))
    application.add_handler(CallbackQueryHandler(create_task_callback_handler, pattern="^(prompt_create_task|bulk_parse_tasks)$"))
    application.add_handler(CallbackQueryHandler(board_callback_handler))

    # 2. Command Router & Channel Post Handlers
    application.add_handler(MessageHandler(filters.Regex(r"^/"), command_router))
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))

    # 3. Text message handler for interactive prompts
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, combined_text_message_handler))

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
        logger.info("Starting polling loop (Bot V2). Press Ctrl+C to stop.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
