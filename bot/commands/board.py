import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import db, github_client, locking
from bot.auth import is_user_admin

logger = logging.getLogger(__name__)


async def get_board_data() -> tuple[str, InlineKeyboardMarkup]:
    """
    Fetches open issues from GitHub, syncs them with SQLite locks,
    and returns a formatted text board and the inline keyboard markup.
    """
    try:
        # 1. Fetch live open issues from GitHub
        open_issues = await github_client.list_github_issues()
    except Exception as e:
        logger.error(f"Error fetching issues from GitHub: {e}")
        return (
            "❌ *Failed to fetch issues from GitHub.*\n"
            f"Please verify your `.env` configuration and credentials.\n\nError: `{str(e)}`",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Retry", callback_data="refresh")]])
        )

    # 2. Sync issues to SQLite database (ensure locks exist)
    for issue in open_issues:
        issue_number = issue["number"]
        lock = db.get_lock(issue_number)
        if not lock:
            # Create a default todo lock
            db.save_lock(db.Lock(
                issue_number=issue_number,
                repo=github_client.GITHUB_PROJECT,
                status="todo"
            ))

    # 3. Fetch locks from DB to construct the current status mapping
    db_locks = {l.issue_number: l for l in db.get_all_locks()}

    # Group issues by status
    todo_list = []
    doing_list = []
    done_list = []

    for issue in open_issues:
        issue_number = issue["number"]
        title = issue["title"]
        url = issue["html_url"]
        
        lock = db_locks.get(issue_number)
        status = lock.status if lock else "todo"
        assignee = lock.locked_by_username if lock else None

        issue_info = {"number": issue_number, "title": title, "url": url, "assignee": assignee}

        if status == "doing":
            doing_list.append(issue_info)
        elif status == "done":
            done_list.append(issue_info)
        else:
            todo_list.append(issue_info)

    # 4. Format board text
    text_lines = ["📊 *Project Kanban Board*\n", "----------------------------\n"]

    text_lines.append("📋 *TODO*")
    if not todo_list:
        text_lines.append("_No tasks to do._")
    for issue in todo_list:
        text_lines.append(f"• [#{issue['number']}]({issue['url']}): {issue['title']}")
    text_lines.append("")

    text_lines.append("🏃 *DOING*")
    if not doing_list:
        text_lines.append("_No tasks in progress._")
    for issue in doing_list:
        text_lines.append(
            f"• [#{issue['number']}]({issue['url']}): {issue['title']} "
            f"👤 @{issue['assignee']}"
        )
    text_lines.append("")

    text_lines.append("✅ *DONE*")
    if not done_list:
        text_lines.append("_No completed tasks open on GitHub._")
    for issue in done_list:
        text_lines.append(
            f"• [#{issue['number']}]({issue['url']}): {issue['title']} "
            f"👤 @{issue['assignee']}"
        )

    # 5. Build keyboard
    keyboard = []

    # Add Claim buttons for todo tasks
    for issue in todo_list:
        keyboard.append([
            InlineKeyboardButton(
                f"➡️ Claim #{issue['number']}", 
                callback_data=f"claim:{issue['number']}"
            )
        ])

    # Add Release / Done buttons for doing tasks
    for issue in doing_list:
        keyboard.append([
            InlineKeyboardButton(
                f"🔓 Release #{issue['number']}", 
                callback_data=f"release:{issue['number']}"
            ),
            InlineKeyboardButton(
                f"✅ Done #{issue['number']}", 
                callback_data=f"done:{issue['number']}"
            )
        ])

    # Add refresh button at the bottom
    keyboard.append([InlineKeyboardButton("🔄 Refresh Board", callback_data="refresh")])

    return "\n".join(text_lines), InlineKeyboardMarkup(keyboard)


async def board_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/board`.
    """
    text, reply_markup = await get_board_data()
    await update.message.reply_text(
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

    await query.answer()  # Always answer callback queries

    if data == "refresh":
        text, reply_markup = await get_board_data()
        try:
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            # Telegram throws error if edited content is identical
            logger.debug(f"Refresh edit error (likely no change): {e}")
        return

    # Parse action and issue number
    action, issue_str = data.split(":", 1)
    issue_number = int(issue_str)

    if action == "claim":
        username = user.username or user.first_name
        result = await locking.claim_card(issue_number, user.id, username)
        
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
        result = await locking.release_card(issue_number, user.id, is_admin=is_admin)

        
        if result == "released":
            alert_text = f"🔓 Released issue #{issue_number} back to TODO."
        elif result == "not_claimed":
            alert_text = "❌ This issue is not currently claimed."
        elif result == "unauthorized":
            lock = db.get_lock(issue_number)
            owner = lock.locked_by_username if lock else "unknown"
            alert_text = f"🔒 Only the claimant (@{owner}) can release this card!"
        else:
            alert_text = "❌ Failed to release issue."

        await query.answer(text=alert_text, show_alert=True if result == "unauthorized" else False)

    elif action == "done":
        result = await locking.mark_card_done(issue_number, user.id)
        
        if result == "marked_done":
            alert_text = f"🎉 Marked issue #{issue_number} as DONE!"
        elif result == "not_claimed":
            alert_text = "❌ This issue is not currently claimed."
        elif result == "unauthorized":
            lock = db.get_lock(issue_number)
            owner = lock.locked_by_username if lock else "unknown"
            alert_text = f"🔒 Only the claimant (@{owner}) can mark this card done!"
        else:
            alert_text = "❌ Failed to update status."

        await query.answer(text=alert_text, show_alert=True if result == "unauthorized" else False)

    # Re-render the board with updated status
    text, reply_markup = await get_board_data()
    try:
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.debug(f"Callback edit error (likely no change): {e}")
