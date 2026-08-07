import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import api_client
from bot.utils import send_reply, edit_reply
from bot.commands.auth import ensure_authenticated

logger = logging.getLogger(__name__)

async def repo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/repo`.
    Lists repositories write-accessible to the authenticated user.
    """
    if not await ensure_authenticated(update, context):
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    
    # Send temporary loading message
    loading_message = await send_reply(
        update, context,
        "🔍 *Fetching your GitHub repositories... Please wait.*",
        parse_mode="Markdown"
    )

    try:
        repos = await api_client.list_user_repos(user_id)
        if not repos:
            await edit_reply(update, context, loading_message,
                "⚠️ *No write-accessible repositories found.*\n\n"
                "Please verify that you have collaborator or owner access to repositories on GitHub.",
                parse_mode="Markdown"
            )
            return

        keyboard = []
        # Limit to top 10 repos for clean Telegram UI pagination fallback
        for r in repos[:10]:
            keyboard.append([InlineKeyboardButton(r, callback_data=f"select_repo:{r}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_reply(update, context, loading_message,
            "📁 *Select an Active Repository:*\n\n"
            "This repository will be used to create issues and track project plans.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error listing user repos: {e}")
        await edit_reply(update, context, loading_message,
            f"❌ *Failed to list repositories.* \nError: `{str(e)}`",
            parse_mode="Markdown"
        )


async def repo_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles repository selection inline button click.
    """
    query = update.callback_query
    data = query.data

    if not data.startswith("select_repo:"):
        return

    await query.answer()

    repo_name = data.split(":", 1)[1]
    user_id = query.from_user.id

    try:
        success = await api_client.select_repo(user_id, repo_name)
        if success:
            await query.edit_message_text(
                f"✅ *Active Repository Configured!*\n\n"
                f"📁 *Selected Repository:* `{repo_name}`\n"
                f"All future issues and Kanban cards will sync to this repository.",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"❌ *Failed to configure repository:* Access verification failed.",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error selecting repository: {e}")
        await query.edit_message_text(
            f"❌ *Error setting repository:* `{str(e)}`",
            parse_mode="Markdown"
        )
