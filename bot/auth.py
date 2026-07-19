import os
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if the user is an administrator.
    1. Returns True if the user's ID is in the ADMIN_USER_IDS env var.
    2. Returns True if the user is a creator/administrator in a group/channel.
    """
    user = update.effective_user
    if not user:
        return False
        
    user_id = user.id
    chat = update.effective_chat

    # 1. Check global admin IDs in .env (comma-separated list of IDs)
    admin_ids_str = os.environ.get("ADMIN_USER_IDS", "")
    if admin_ids_str:
        try:
            global_admins = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
            if user_id in global_admins:
                return True
        except ValueError:
            logger.error("Invalid ADMIN_USER_IDS format in environment config. Must be comma-separated integers.")

    # 2. Check chat administrators if we are in a group/supergroup/channel
    if chat and chat.type in [chat.GROUP, chat.SUPERGROUP, chat.CHANNEL]:
        try:
            member = await context.bot.get_chat_member(chat_id=chat.id, user_id=user_id)
            if member.status in ["creator", "administrator"]:
                return True
        except Exception as e:
            logger.error(f"Error checking Telegram group admin status for user {user_id}: {e}")

    return False

def admin_only(func):
    """
    Decorator to restrict command access to administrators only.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not await is_user_admin(update, context):
            # If it's a command, reply with access denied message.
            if update.message:
                await update.message.reply_text(
                    "⛔ *Access Denied:* Only administrators can use this command.",
                    parse_mode="Markdown"
                )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
