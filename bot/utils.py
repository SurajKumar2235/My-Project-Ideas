"""
Utility functions for bot handlers.
"""
import logging
from telegram import Update, Message
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 3500


def split_long_message(text: str, max_chars: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split a long Telegram message into safe-sized chunks while preserving the original text exactly."""
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            split_at = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
            if split_at > start + max_chars * 0.6:
                end = split_at

        if end <= start:
            end = min(start + max_chars, len(text))

        chunk = text[start:end]
        if chunk:
            chunks.append(chunk)
        start = end

    return chunks or [text]


async def send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = None, **kwargs) -> Message:
    """
    Send a reply that works for both regular messages and channel posts.
    Channel posts don't support reply_text, so we use send_message instead.
    Includes fallback to plain text if Telegram Markdown parsing fails.
    """
    if len(text) > TELEGRAM_MESSAGE_LIMIT:
        chunks = split_long_message(text, TELEGRAM_MESSAGE_LIMIT)
        first_kwargs = dict(kwargs)
        first_reply_markup = first_kwargs.pop("reply_markup", None)
        first_msg = None
        for index, chunk in enumerate(chunks):
            chunk_kwargs = dict(first_kwargs)
            if index == 0 and first_reply_markup is not None:
                chunk_kwargs["reply_markup"] = first_reply_markup
            if index == 0:
                first_msg = await send_reply(update, context, chunk, parse_mode=parse_mode, **chunk_kwargs)
            else:
                await send_reply(update, context, chunk, parse_mode=parse_mode, **chunk_kwargs)
        return first_msg

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
    if len(text) > TELEGRAM_MESSAGE_LIMIT:
        try:
            await message.delete()
        except Exception:
            pass
        chunks = split_long_message(text, TELEGRAM_MESSAGE_LIMIT)
        first_kwargs = dict(kwargs)
        first_reply_markup = first_kwargs.pop("reply_markup", None)
        for index, chunk in enumerate(chunks):
            chunk_kwargs = dict(first_kwargs)
            if index == 0 and first_reply_markup is not None:
                chunk_kwargs["reply_markup"] = first_reply_markup
            await send_reply(update, context, chunk, parse_mode=parse_mode, **chunk_kwargs)
        return

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

