import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot_v2 import api_client
from bot_v2.utils import send_reply, edit_reply
from bot_v2.commands.auth import ensure_authenticated

logger = logging.getLogger(__name__)

async def push_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/push`.
    Pushes the active draft as a new GitHub issue and initializes Kanban lock.
    """
    if not await ensure_authenticated(update, context):
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id

    loading_msg = await send_reply(
        update, context,
        "🚀 *Pushing draft project plan to GitHub...*\n_Creating issue and setting status to TODO..._",
        parse_mode="Markdown"
    )

    try:
        res = await api_client.push_draft(user_id, chat_id)
        issue_number = res.get("issue_number")
        html_url = res.get("html_url")
        title = res.get("title")
        repo = res.get("repo")

        msg_text = (
            f"🎉 *Successfully Pushed to GitHub!*\n\n"
            f"📌 *Issue #:* `{issue_number}`\n"
            f"📝 *Title:* {title}\n"
            f"📁 *Repository:* `{repo}`\n"
            f"🔗 *URL:* [{html_url}]({html_url})\n\n"
            "This issue is now listed on your `/board` under **TODO**."
        )

        keyboard = [[InlineKeyboardButton("📊 View Kanban Board", callback_data="refresh_board")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await edit_reply(update, context, loading_msg, msg_text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error pushing draft: {e}")
        await edit_reply(update, context, loading_msg, f"❌ *Error pushing to GitHub:* `{str(e)}`", parse_mode="Markdown")


async def push_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `push_draft:<draft_id>` button click.
    """
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("push_draft:"):
        return

    await query.answer("Pushing draft to GitHub...")
    draft_id = int(query.data.split("push_draft:")[1])
    user_id = query.from_user.id
    chat_id = query.message.chat_id if query.message else user_id

    try:
        res = await api_client.push_draft(user_id, chat_id, draft_id=draft_id)
        issue_number = res.get("issue_number")
        html_url = res.get("html_url")
        title = res.get("title")
        repo = res.get("repo")

        text = (
            f"🎉 *Successfully Pushed Draft #{draft_id} to GitHub!*\n\n"
            f"📌 *Issue #:* `{issue_number}`\n"
            f"📝 *Title:* {title}\n"
            f"📁 *Repository:* `{repo}`\n"
            f"🔗 *URL:* [{html_url}]({html_url})\n\n"
            "Added to your `/board` under **TODO**."
        )

        keyboard = [[InlineKeyboardButton("📊 View Kanban Board", callback_data="refresh_board")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await edit_reply(update, context, query.message, text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error pushing draft #{draft_id}: {e}")
        await query.answer(f"Error: {str(e)}", show_alert=True)
