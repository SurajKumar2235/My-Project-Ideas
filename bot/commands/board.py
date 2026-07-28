import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import api_client
from bot.commands.auth import ensure_authenticated
from bot.auth import is_user_admin

logger = logging.getLogger(__name__)


async def get_board_data(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """
    Fetches the Kanban board data for the user's active repository from the backend
    and returns a formatted text board and the inline keyboard markup.
    """
    try:
        board = await api_client.get_board(telegram_id)
    except Exception as e:
        logger.error(f"Error fetching board data: {e}")
        return (
            "❌ *Failed to fetch board data from backend.*\n"
            f"Please verify your `/login` status.\n\nError: `{str(e)}`",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Retry", callback_data="refresh_board")]])
        )

    repo = board.get("repo", "Default")
    todo_list = board.get("todo", [])
    doing_list = board.get("doing", [])
    done_list = board.get("done", [])

    # Format board text
    text_lines = [
        f"📊 *Kanban Board: `{repo}`*\n",
        "----------------------------\n"
    ]

    text_lines.append("📋 *TODO*")
    if not todo_list:
        text_lines.append("_No tasks to do._")
    for issue in todo_list:
        text_lines.append(f"• [#{issue['number']}]({issue['html_url']}): {issue['title']}")
    text_lines.append("")

    text_lines.append("🏃 *DOING*")
    if not doing_list:
        text_lines.append("_No tasks in progress._")
    for issue in doing_list:
        text_lines.append(
            f"• [#{issue['number']}]({issue['html_url']}): {issue['title']} "
            f"👤 @{issue['assignee']}"
        )
    text_lines.append("")

    text_lines.append("✅ *DONE*")
    if not done_list:
        text_lines.append("_No completed tasks open on GitHub._")
    for issue in done_list:
        text_lines.append(
            f"• [#{issue['number']}]({issue['html_url']}): {issue['title']} "
            f"👤 @{issue['assignee']}"
        )

    # Build keyboard
    keyboard = []

    # Add Claim buttons for todo tasks (limit to fit Telegram API limits)
    # Callback format: claim:<number>:<repo>
    for issue in todo_list[:8]:
        keyboard.append([
            InlineKeyboardButton(
                f"➡️ Claim #{issue['number']}", 
                callback_data=f"claim:{issue['number']}:{repo}"
            )
        ])

    # Add Release / Done buttons for doing tasks
    # Callback format: release/done:<number>:<repo>
    for issue in doing_list[:8]:
        keyboard.append([
            InlineKeyboardButton(
                f"🔓 Release #{issue['number']}", 
                callback_data=f"release:{issue['number']}:{repo}"
            ),
            InlineKeyboardButton(
                f"✅ Done #{issue['number']}", 
                callback_data=f"done:{issue['number']}:{repo}"
            )
        ])

    # Add refresh button at the bottom
    keyboard.append([InlineKeyboardButton("🔄 Refresh Board", callback_data="refresh_board")])

    return "\n".join(text_lines), InlineKeyboardMarkup(keyboard)


async def board_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/board`.
    """
    if not await ensure_authenticated(update, context):
        return

    user_id = update.effective_user.id
    
    # Send loading text
    loading_message = await update.message.reply_text(
        "📊 *Loading board...*",
        parse_mode="Markdown"
    )

    text, reply_markup = await get_board_data(user_id)
    await loading_message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )


async def board_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles inline keyboard clicks on the board.
    """
    query = update.callback_query
    user = query.from_user
    data = query.data

    if not data:
        return

    await query.answer()

    if data == "refresh_board":
        text, reply_markup = await get_board_data(user.id)
        try:
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.debug(f"Refresh board edit error (likely no change): {e}")
        return

    # Parse action, issue number, and repo
    # Format: action:issue_number:repo_name
    parts = data.split(":")
    if len(parts) < 3:
        return
        
    action = parts[0]
    issue_number = int(parts[1])
    repo = ":".join(parts[2:]) # Handle repo names with colons if any

    if action == "claim":
        username = user.username or user.first_name
        result = await api_client.claim_card(user.id, username, issue_number, repo)
        
        if result == "claimed":
            alert_text = f"✅ You successfully claimed issue #{issue_number}!"
        elif result == "already_claimed_by_you":
            alert_text = "ℹ️ You have already claimed this issue."
        elif result == "already_claimed_by_other":
            alert_text = "❌ This issue has already been claimed by someone else!"
        elif result == "already_done":
            alert_text = "❌ This issue is already completed."
        else:
            alert_text = "❌ Failed to claim issue."

        await query.answer(text=alert_text, show_alert=True if "already_claimed_by_other" in result else False)

    elif action == "release":
        is_admin = await is_user_admin(update, context)
        result = await api_client.release_card(user.id, issue_number, repo, is_admin=is_admin)
        
        if result == "released":
            alert_text = f"🔓 Released issue #{issue_number} back to TODO."
        elif result == "not_claimed":
            alert_text = "❌ This issue is not currently claimed."
        elif result == "unauthorized":
            alert_text = f"🔒 Only the claimant or an admin can release this card!"
        else:
            alert_text = "❌ Failed to release issue."

        await query.answer(text=alert_text, show_alert=True if result == "unauthorized" else False)

    elif action == "done":
        result = await api_client.mark_card_done(user.id, issue_number, repo)
        
        if result == "marked_done":
            alert_text = f"🎉 Marked issue #{issue_number} as DONE!"
        elif result == "not_claimed":
            alert_text = "❌ This issue is not currently claimed."
        elif result == "unauthorized":
            alert_text = f"🔒 Only the claimant can mark this card done!"
        else:
            alert_text = "❌ Failed to update status."

        await query.answer(text=alert_text, show_alert=True if result == "unauthorized" else False)

    # Re-render the board with updated status
    text, reply_markup = await get_board_data(user.id)
    try:
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.debug(f"Callback edit error (likely no change): {e}")
