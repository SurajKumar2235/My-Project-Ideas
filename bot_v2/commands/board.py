import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot_v2 import api_client
from bot_v2.utils import send_reply, edit_reply
from bot_v2.commands.auth import ensure_authenticated

logger = logging.getLogger(__name__)

async def board_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/board`.
    Fetches and renders the Kanban board columns (TODO, DOING, DONE) with interactive action buttons.
    """
    if not await ensure_authenticated(update, context):
        return

    user_id = update.effective_user.id
    
    try:
        board_data = await api_client.get_board(user_id)
        text, reply_markup = format_board_message(board_data)
        await send_reply(update, context, text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error fetching board: {e}")
        await send_reply(
            update, context,
            f"❌ *Error loading Kanban board:* `{str(e)}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Retry", callback_data="refresh_board")]]),
            parse_mode="Markdown"
        )


def format_board_message(board_data: dict) -> tuple[str, InlineKeyboardMarkup]:
    """
    Formats board dictionary into readable Markdown text and inline keyboard buttons.
    """
    repo = board_data.get("repo", "Unknown Repo")
    todo_list = board_data.get("todo", [])
    doing_list = board_data.get("doing", [])
    done_list = board_data.get("done", [])

    text_lines = [
        f"📊 *Kanban Project Board*\n📁 *Repository:* `{repo}`\n",
        f"📥 *TODO ({len(todo_list)})*"
    ]

    if not todo_list:
        text_lines.append("  _No pending tasks_")
    else:
        for item in todo_list[:10]:
            text_lines.append(f"  • #{item['number']}: [{item['title']}]({item['html_url']})")

    text_lines.append(f"\n🚧 *DOING ({len(doing_list)})*")
    if not doing_list:
        text_lines.append("  _No active tasks_")
    else:
        for item in doing_list[:10]:
            assignee = f" (@{item['assignee']})" if item.get('assignee') else ""
            text_lines.append(f"  • #{item['number']}: [{item['title']}]({item['html_url']}){assignee}")

    text_lines.append(f"\n✅ *DONE ({len(done_list)})*")
    if not done_list:
        text_lines.append("  _No completed tasks_")
    else:
        for item in done_list[:5]:
            text_lines.append(f"  • #{item['number']}: [{item['title']}]({item['html_url']})")

    keyboard = []
    # Claim buttons for TODO tasks
    for issue in todo_list[:6]:
        keyboard.append([
            InlineKeyboardButton(
                f"➡️ Claim #{issue['number']}",
                callback_data=f"claim:{issue['number']}:{repo}"
            )
        ])

    # Release / Done buttons for DOING tasks
    for issue in doing_list[:6]:
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

    keyboard.append([
        InlineKeyboardButton("➕ Create Task", callback_data="prompt_create_task"),
        InlineKeyboardButton("🔄 Refresh Board", callback_data="refresh_board")
    ])
    return "\n".join(text_lines), InlineKeyboardMarkup(keyboard)


async def board_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles Kanban board inline button interactions (claim, release, done, refresh).
    """
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name or f"User_{user_id}"

    try:
        if data == "refresh_board":
            await query.answer("Refreshing board...")
            board_data = await api_client.get_board(user_id)
            text, reply_markup = format_board_message(board_data)
            await edit_reply(update, context, query.message, text, reply_markup=reply_markup, parse_mode="Markdown")
            return

        parts = data.split(":", 2)
        if len(parts) < 3:
            return

        action, issue_str, repo = parts[0], parts[1], parts[2]
        issue_number = int(issue_str)

        if action == "claim":
            res = await api_client.claim_card(user_id, username, issue_number, repo)
            if res == "claimed":
                await query.answer(f"Claimed issue #{issue_number}!", show_alert=False)
            elif res == "already_claimed_by_you":
                await query.answer(f"You already claimed issue #{issue_number}.", show_alert=True)
            elif res == "already_claimed_by_other":
                await query.answer(f"Issue #{issue_number} is already claimed by someone else.", show_alert=True)
            elif res == "already_done":
                await query.answer(f"Issue #{issue_number} is already completed.", show_alert=True)

        elif action == "release":
            res = await api_client.release_card(user_id, issue_number, repo)
            if res == "released":
                await query.answer(f"Released issue #{issue_number}.", show_alert=False)
            elif res == "unauthorized":
                await query.answer(f"You can only release tasks claimed by you.", show_alert=True)
            else:
                await query.answer(f"Task is not currently claimed.", show_alert=True)

        elif action == "done":
            res = await api_client.mark_card_done(user_id, issue_number, repo)
            if res == "marked_done":
                await query.answer(f"Completed issue #{issue_number}! 🎉", show_alert=False)
            elif res == "unauthorized":
                await query.answer(f"You can only mark tasks claimed by you as done.", show_alert=True)
            else:
                await query.answer(f"Task is not currently in progress.", show_alert=True)

        # Refresh board after action
        board_data = await api_client.get_board(user_id)
        text, reply_markup = format_board_message(board_data)
        await edit_reply(update, context, query.message, text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error handling board callback {data}: {e}")
        await query.answer(f"Error: {str(e)}", show_alert=True)
