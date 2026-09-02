import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot_v2 import api_client
from bot_v2.utils import send_reply, edit_reply
from bot_v2.commands.auth import ensure_authenticated

logger = logging.getLogger(__name__)

async def repo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/repo`.
    Lists write-accessible GitHub repositories and presents an interactive selector.
    """
    if not await ensure_authenticated(update, context):
        return

    user_id = update.effective_user.id
    
    try:
        auth_status = await api_client.identify_user(user_id)
        user_data = auth_status.get("user", {})
        active_repo = user_data.get("active_repo")

        repos = await api_client.list_user_repos(user_id)
        if not repos:
            await send_reply(
                update, context,
                "⚠️ *No Repositories Found*\n\n"
                "No write-accessible GitHub repositories were found for your account.\n"
                "Ensure your token or GitHub user has push permissions.",
                parse_mode="Markdown"
            )
            return

        keyboard = []
        for r in repos:
            label = f"✅ {r}" if r == active_repo else r
            keyboard.append([InlineKeyboardButton(label, callback_data=f"select_repo:{r}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        msg_text = (
            "📁 *Select Active Repository*\n\n"
            f"Current Active Repo: `{active_repo or 'None (using global default)'}`\n\n"
            "Click a repository below to set it as your target for plans, tasks, and board operations:"
        )

        await send_reply(update, context, msg_text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error listing repositories: {e}")
        await send_reply(update, context, f"❌ *Error listing repos:* `{str(e)}`", parse_mode="Markdown")


async def repo_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles inline button clicks for repository selection (`select_repo:<repo_name>`).
    """
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("select_repo:"):
        return

    repo_name = query.data.split("select_repo:", 1)[1]
    user_id = query.from_user.id
    logger.info(f"Received select_repo callback for '{repo_name}' from user {user_id}")

    try:
        await query.answer(f"Selecting {repo_name}...")
        res = await api_client.select_repo(user_id, repo_name)
        active_repo = res.get("active_repo", repo_name)
        username = res.get("username", query.from_user.first_name if query.from_user else "User")

        # Re-fetch repo list to show updated active badge ✅
        repos = await api_client.list_user_repos(user_id)
        keyboard = []
        for r in repos:
            label = f"✅ {r}" if r == active_repo else r
            keyboard.append([InlineKeyboardButton(label, callback_data=f"select_repo:{r}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"✅ *Active Repository Updated!*\n\n"
            f"👤 *User:* `{username}`\n"
            f"📁 *Current Active Repo:* `{active_repo}`\n\n"
            "All future `/plan`, `/push`, `/create_task`, and `/board` commands will target this repository.\n\n"
            "Click a repository below to switch target repo:"
        )

        await edit_reply(update, context, query.message, text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error selecting repository {repo_name}: {e}")
        await query.answer(f"Error selecting repository: {str(e)}", show_alert=True)
