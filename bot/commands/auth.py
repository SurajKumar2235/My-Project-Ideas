import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import api_client
from bot.utils import send_reply

logger = logging.getLogger(__name__)

async def ensure_authenticated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if the user has linked their GitHub account.
    If not, sends the OAuth login button and returns False.
    """
    if not update.effective_user:
        await send_reply(
            update, context,
            "ℹ️ *Channel Notice:* Telegram channels do not provide individual user IDs to bots.\n\n"
            "To manage GitHub repos, plans, and tasks, please run commands in a private chat with the bot or in a group chat.",
            parse_mode="Markdown"
        )
        return False

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id
    message_target = update.message or (update.callback_query.message if update.callback_query else None) or update.channel_post

    if not message_target:
        return False

    try:
        auth_status = await api_client.identify_user(user_id)
        if not auth_status.get("authenticated", False):
            login_url = await api_client.get_login_link(user_id, chat_id)
            keyboard = [[InlineKeyboardButton("🔗 Connect GitHub Account", url=login_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg_text = (
                "🔒 *Authentication Required*\n\n"
                "You need to link your GitHub account to use this bot.\n"
                "Click the button below to sign in with GitHub OAuth."
            )
            
            if update.callback_query:
                await update.callback_query.answer("Authentication required.", show_alert=True)
                await message_target.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
            else:
                await send_reply(update, context, msg_text, parse_mode="Markdown", reply_markup=reply_markup)
            return False
            
        return True
    except Exception as e:
        logger.error(f"Failed to check authentication: {e}")
        await send_reply(update, context, f"❌ *Authentication Error:* `{str(e)}`", parse_mode="Markdown")
        return False


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/login`.
    """
    if not update.effective_user:
        await send_reply(
            update, context,
            "ℹ️ *Channel Notice:* Telegram channels do not provide individual user IDs to bots.\n\n"
            "Please send `/login` in a private chat with the bot to link your GitHub account.",
            parse_mode="Markdown"
        )
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id
    
    try:
        auth_status = await api_client.identify_user(user_id)
        if auth_status.get("authenticated", False):
            user_data = auth_status.get("user", {})
            active_repo = user_data.get("active_repo") or "None (push to default)"
            await send_reply(
                update, context,
                f"✅ *Already Connected!*\n\n"
                f"👤 *GitHub User:* {user_data.get('username')}\n"
                f"📁 *Active Repo:* `{active_repo}`\n\n"
                "Use `/repo` to select a different repository.",
                parse_mode="Markdown"
            )
            return

        login_url = await api_client.get_login_link(user_id, chat_id)
        keyboard = [[InlineKeyboardButton("🔗 Connect GitHub Account", url=login_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_reply(
            update, context,
            "🔑 *GitHub OAuth Linkage*\n\n"
            "To manage projects and tasks, please link your GitHub account by clicking below.\n"
            "Once completed, this bot will notify you.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in login command: {e}")
        await send_reply(update, context, f"❌ *Error:* `{str(e)}`", parse_mode="Markdown")


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/logout`.
    Disassociates the GitHub account.
    """
    if not update.effective_user:
        await send_reply(
            update, context,
            "ℹ️ *Channel Notice:* Telegram channels do not provide individual user IDs to bots.\n\n"
            "Please send `/logout` in a private chat with the bot.",
            parse_mode="Markdown"
        )
        return

    user_id = update.effective_user.id
    
    try:
        auth_status = await api_client.identify_user(user_id)
        if not auth_status.get("authenticated", False):
            await send_reply(
                update, context,
                "ℹ️ *Not Connected*\n\n"
                "You are not currently linked to any GitHub account.",
                parse_mode="Markdown"
            )
            return

        user_data = auth_status.get("user", {})
        username = user_data.get("username", "Unknown")

        await api_client.logout_user(user_id)
        
        await send_reply(
            update, context,
            f"👋 *Logged Out Successfully!*\n\n"
            f"GitHub account *{username}* has been disassociated from this Telegram account.\n"
            "Use `/login` whenever you want to connect a GitHub account again.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in logout command: {e}")
        await send_reply(update, context, f"❌ *Logout Error:* `{str(e)}`", parse_mode="Markdown")

