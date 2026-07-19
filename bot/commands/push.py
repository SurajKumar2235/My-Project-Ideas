import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot import db, github_client

from bot.auth import admin_only, is_user_admin

logger = logging.getLogger(__name__)

async def _do_push(chat_id: int, user_id: int, draft, message_target) -> None:
    """Helper to push a specific draft to GitHub and edit the target message with the result."""
    content = draft.content.strip()
    lines = content.split("\n")
    
    # Extract title from the first line
    first_line = lines[0] if lines else "Untitled Idea"
    title = first_line.lstrip("#").strip()
    
    # The body is everything after the first line
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

    try:
        # Call GitHub client to create the issue
        issue = await github_client.create_github_issue(title, body)
        issue_number = issue.get("number")
        html_url = issue.get("html_url")

        # Save initial lock entry in SQLite
        db.save_lock(db.Lock(
            issue_number=issue_number,
            repo=github_client.GITHUB_PROJECT,
            status="todo"
        ))

        # Delete draft since it has been successfully pushed
        db.delete_draft_by_id(draft.id)

        # Success message
        await message_target.edit_text(
            f"✅ *Issue Created Successfully!*\n\n"
            f"📌 **Issue:** [#{issue_number}]({html_url}) - {title}\n"
            f"📁 **Status:** `todo`\n\n"
            "Use `/board` to view active cards and claim tasks.",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.exception("Error while pushing draft to GitHub:")
        await message_target.edit_text(
            f"❌ *Failed to push to GitHub.* \nError: `{str(e)}`",
            parse_mode="Markdown"
        )


@admin_only
async def push_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/push`.
    Pushes the user's draft to GitHub. If multiple exist, prompts with inline keyboard.
    """
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Retrieve all drafts for this user
    drafts = db.get_all_user_drafts(chat_id, user_id)
    if not drafts:
        await update.message.reply_text(
            "📝 *No drafts found.* \nUse `/plan <idea>` to generate a plan draft first.",
            parse_mode="Markdown"
        )
        return

    # If only one draft, push it immediately
    if len(drafts) == 1:
        loading_message = await update.message.reply_text(
            "🚀 *Creating GitHub Issue... Please wait.*",
            parse_mode="Markdown"
        )
        await _do_push(chat_id, user_id, drafts[0], loading_message)
        return

    # If multiple drafts exist, create an inline keyboard menu
    keyboard = []
    for d in drafts:
        title = d.content.split("\n")[0].lstrip("#").strip()
        # limit length of title for button aesthetics
        display_title = (title[:30] + '...') if len(title) > 30 else title
        keyboard.append([InlineKeyboardButton(f"Push: {display_title}", callback_data=f"push_draft:{d.id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📂 **You have multiple pending drafts.** Please select which one to push:",
        reply_markup=reply_markup,
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

    draft_id_str = data.split(":")[1]
    draft_id = int(draft_id_str)
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Verify draft exists and belongs to this user
    draft = db.get_draft_by_id(draft_id)
    if not draft or draft.user_id != user_id or draft.chat_id != chat_id:
        await query.edit_message_text(
            "❌ *This draft is no longer available or you do not have permission.*", 
            parse_mode="Markdown"
        )
        return

    # Update the keyboard message to a loading state
    await query.edit_message_text(
        "🚀 *Creating GitHub Issue... Please wait.*",
        parse_mode="Markdown"
    )
    
    # Push the selected draft
    await _do_push(chat_id, user_id, draft, query.message)
