import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot import api_client
from bot.commands.auth import ensure_authenticated
from bot.auth import admin_only, is_user_admin
from bot.utils import send_reply, edit_reply

logger = logging.getLogger(__name__)

async def _do_push(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int, draft_id: int, loading_message) -> None:
    """Helper to push a specific draft to GitHub via the API and show the result."""
    try:
        res = await api_client.push_draft(user_id, chat_id, draft_id)
        
        issue_number = res.get("issue_number")
        html_url = res.get("html_url")
        title = res.get("title")
        repo = res.get("repo")

        # Success message
        await edit_reply(update, context, loading_message,
            f"✅ *Issue Created Successfully!*\n\n"
            f"📌 *Issue:* [#{issue_number}]({html_url}) - {title}\n"
            f"📁 *Repository:* `{repo}`\n"
            f"📁 *Status:* `todo`\n\n"
            "Use `/board` to view active cards and claim tasks.",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.exception("Error while pushing draft to GitHub:")
        await edit_reply(update, context, loading_message,
            f"❌ *Failed to push to GitHub.* \nError: `{str(e)}`",
            parse_mode="Markdown"
        )


@admin_only
async def push_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/push`.
    Pushes the user's draft to GitHub. If multiple exist, prompts with inline keyboard.
    """
    if not await ensure_authenticated(update, context):
        return

    if not update.effective_user or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    try:
        # Retrieve all drafts for this user
        drafts = await api_client.list_drafts(user_id, chat_id)
        if not drafts:
            await send_reply(update, context,
                "🗐️ *No drafts found.* \nUse `/plan <idea>` to generate a plan draft first.",
                parse_mode="Markdown"
            )
            return

        # If only one draft, push it immediately
        if len(drafts) == 1:
            loading_message = await send_reply(update, context,
                "🚀 *Creating GitHub Issue... Please wait.*",
                parse_mode="Markdown"
            )
            await _do_push(update, context, user_id, chat_id, drafts[0]["id"], loading_message)
            return

        # If multiple drafts exist, create an inline keyboard menu
        keyboard = []
        for d in drafts:
            content = d["content"].strip()
            first_line = content.split("\n")[0] if content else "Untitled Idea"
            title = first_line.lstrip("#").strip()
            # limit length of title for button aesthetics
            display_title = (title[:30] + '...') if len(title) > 30 else title
            keyboard.append([InlineKeyboardButton(f"Push: {display_title}", callback_data=f"push_draft:{d['id']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_reply(update, context,
            "📂 *You have multiple pending drafts.* Please select which one to push:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error fetching drafts list: {e}")
        await send_reply(update, context,
            f"❌ *Error retrieving drafts:* `{str(e)}`",
            parse_mode="Markdown"
        )


async def push_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles inline keyboard clicks for selecting a draft to push.
    """
    query = update.callback_query
    data = query.data

    if not data.startswith("push_draft:"):
        return

    # Verify admin permissions for callback
    if not await is_user_admin(update, context):
        await query.answer("⛔ Access Denied: Only administrators can push drafts.", show_alert=True)
        return
        
    await query.answer()

    if not update.effective_user or not update.effective_chat:
        return

    draft_id_str = data.split(":")[1]
    draft_id = int(draft_id_str)
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Update the keyboard message to a loading state
    await query.edit_message_text(
        "🚀 *Creating GitHub Issue... Please wait.*",
        parse_mode="Markdown"
    )
    
    # Push the selected draft
    await _do_push(update, context, user_id, chat_id, draft_id, query.message)
