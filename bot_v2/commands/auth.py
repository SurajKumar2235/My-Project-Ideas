import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot_v2 import api_client
from bot_v2.utils import send_reply

logger = logging.getLogger(__name__)

def is_localhost_url(url: str) -> bool:
    """Checks if a URL points to localhost or 127.0.0.1 or 0.0.0.0."""
    url_lower = url.lower()
    return "localhost" in url_lower or "127.0.0.1" in url_lower or "0.0.0.0" in url_lower


def build_auth_reply_content(login_url: str, header: str, body: str) -> tuple[str, InlineKeyboardMarkup | None]:
    """
    Returns (msg_text, reply_markup).
    If login_url is a localhost URL, Telegram API rejects InlineKeyboardButton(url=...),
    so we include the clickable link directly in the message text.
    If login_url is a public domain, we provide an InlineKeyboardButton.
    """
    if is_localhost_url(login_url):
        msg_text = (
            f"{header}\n\n"
            f"{body}\n\n"
            f"🔗 [Click here to Connect GitHub Account]({login_url})\n\n"
            f"*(Direct Link: `{login_url}`)*"
        )
        return msg_text, None
    else:
        keyboard = [[InlineKeyboardButton("🔗 Connect GitHub Account", url=login_url)]]
        msg_text = (
            f"{header}\n\n"
            f"{body}\n\n"
            f"🔗 [Connect GitHub Account]({login_url})"
        )
        return msg_text, InlineKeyboardMarkup(keyboard)


async def ensure_authenticated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if the user has linked their GitHub account.
    If not, sends the OAuth login button or link and returns False.
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
            header = "🔒 *Authentication Required*"
            body = "You need to link your GitHub account to use this bot."
            msg_text, reply_markup = build_auth_reply_content(login_url, header, body)
            
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
            role = user_data.get("role", "user")
            await send_reply(
                update, context,
                f"✅ *Already Connected!*\n\n"
                f"👤 *GitHub User:* {user_data.get('username')}\n"
                f"🛡 *Role:* `{role}`\n"
                f"📁 *Active Repo:* `{active_repo}`\n\n"
                "Use `/repo` to select a different repository.",
                parse_mode="Markdown"
            )
            return

        login_url = await api_client.get_login_link(user_id, chat_id)
        header = "🔑 *GitHub OAuth Linkage*"
        body = "To manage projects and tasks, please link your GitHub account by clicking below.\nOnce completed, this bot will notify you."
        msg_text, reply_markup = build_auth_reply_content(login_url, header, body)

        await send_reply(
            update, context,
            msg_text,
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
