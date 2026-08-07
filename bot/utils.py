"""
Utility functions for bot handlers.
"""
import logging
from telegram import Update, Message
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = None, **kwargs) -> Message:
    """
    Send a reply that works for both regular messages and channel posts.
    Channel posts don't support reply_text, so we use send_message instead.
    Includes fallback to plain text if Telegram Markdown parsing fails.
    """
    try:
        if update.message:
            logger.debug("Sending reply to regular message")
            result = await update.message.reply_text(text, parse_mode=parse_mode, **kwargs)
            if result is None:
                raise ValueError("reply_text returned None")
            return result
        elif update.channel_post:
            logger.debug(f"Sending message to channel {update.channel_post.chat_id}")
            result = await context.bot.send_message(
                chat_id=update.channel_post.chat_id,
                text=text,
                parse_mode=parse_mode,
                **kwargs
            )
            if result is None:
                raise ValueError("send_message returned None")
            return result
    except Exception as e:
        if parse_mode:
            logger.warning(f"send_reply failed with parse_mode={parse_mode}: {e}. Retrying with parse_mode=None.")
            if update.message:
                return await update.message.reply_text(text, parse_mode=None, **kwargs)
            elif update.channel_post:
                return await context.bot.send_message(
                    chat_id=update.channel_post.chat_id,
                    text=text,
                    parse_mode=None,
                    **kwargs
                )
        raise

    logger.error(f"send_reply called but neither update.message nor update.channel_post is set. Update: {update}")
    raise ValueError("Cannot send reply: no message or channel_post in update")


async def edit_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, message, text: str, parse_mode: str = None, **kwargs) -> None:
    """
    Edit a previously sent message, works for both regular messages and channel posts.
    Includes fallback to plain text if Markdown parsing fails.
    """
    if message and hasattr(message, 'edit_text'):
        try:
            await message.edit_text(text, parse_mode=parse_mode, **kwargs)
            return
        except Exception as e:
            if parse_mode:
                logger.warning(f"edit_reply edit_text failed with parse_mode={parse_mode}: {e}. Retrying edit_text with parse_mode=None.")
                try:
                    await message.edit_text(text, parse_mode=None, **kwargs)
                    return
                except Exception as e2:
                    logger.warning(f"edit_reply fallback edit_text with parse_mode=None failed: {e2}. Deleting and sending new message.")
            
            # Fallback: delete and resend if edit fails
            try:
                await message.delete()
            except Exception:
                pass
            await send_reply(update, context, text, parse_mode=parse_mode, **kwargs)

