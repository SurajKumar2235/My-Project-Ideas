import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot_v2 import api_client
from bot_v2.utils import send_reply
from bot_v2.commands.auth import ensure_authenticated

logger = logging.getLogger(__name__)

async def create_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/create_task [task_title]`.
    If task_title is provided, creates a single task GitHub issue.
    If no argument is provided, prompts the user to enter task details or parse draft checkboxes.
    """
    if not await ensure_authenticated(update, context):
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id

    task_title = " ".join(context.args) if context.args else None

    if task_title:
        await execute_create_single_task(update, context, user_id, chat_id, task_title)
    else:
        # Prompt user to enter task title or bulk parse draft tasks
        keyboard = [
            [
                InlineKeyboardButton("✍️ Enter Task Title & Details", callback_data="prompt_create_task"),
                InlineKeyboardButton("📦 Bulk Parse Draft Tasks", callback_data="bulk_parse_tasks")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_reply(
            update, context,
            "🛠 *Create GitHub Task*\n\n"
            "Choose an option below:\n"
            "1. Click **Enter Task Title** to write task details directly.\n"
            "2. Click **Bulk Parse Draft Tasks** to create tasks from `- [ ]` checkboxes in your plan draft.\n\n"
            "*(Or type `/create_task <your task title>` directly)*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


async def execute_create_single_task(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int, task_title: str) -> None:
    """
    Executes single task creation on GitHub.
    """
    loading_msg = await send_reply(
        update, context,
        f"🛠 *Creating GitHub issue for task:* `{task_title}`...",
        parse_mode="Markdown"
    )
    try:
        res = await api_client.create_task(user_id, chat_id, task_title=task_title)
        issue_number = res.get("issue_number")
        html_url = res.get("html_url")
        repo = res.get("repo")

        msg_text = (
            f"✅ *Task Issue Created Successfully!*\n\n"
            f"📌 *Issue #:* `{issue_number}`\n"
            f"📝 *Title:* {task_title}\n"
            f"📁 *Repository:* `{repo}`\n"
            f"🔗 *URL:* [{html_url}]({html_url})"
        )
        keyboard = [[InlineKeyboardButton("📊 View Board", callback_data="refresh_board")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_reply(update, context, msg_text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error creating single task: {e}")
        await send_reply(update, context, f"❌ *Error creating task:* `{str(e)}`", parse_mode="Markdown")


async def create_task_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles inline buttons for task creation (`prompt_create_task`, `bulk_parse_tasks`).
    """
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat_id if query.message else user_id

    if data == "prompt_create_task":
        await query.answer()
        context.user_data["awaiting_task_title"] = True
        await send_reply(
            update, context,
            "✍️ *Enter Task Title & Details*\n\n"
            "Reply with the title and details of the GitHub issue you would like to create.",
            parse_mode="Markdown"
        )

    elif data == "bulk_parse_tasks":
        await query.answer("Parsing draft tasks...")
        try:
            res = await api_client.create_task(user_id, chat_id)
            req_type = res.get("type")

            if req_type == "bulk":
                created = res.get("created", [])
                failed = res.get("failed", [])
                repo = res.get("repo", "Default Repo")

                if not created and not failed:
                    await send_reply(
                        update, context,
                        "ℹ️ *No Checkbox Tasks Found*\n\n"
                        "No `- [ ] task` items were found in your active project draft.",
                        parse_mode="Markdown"
                    )
                    return

                text_lines = [
                    f"🎉 *Bulk Task Creation Summary*\n📁 *Repository:* `{repo}`\n",
                    f"✅ *Created Issues ({len(created)}):*"
                ]
                for item in created:
                    text_lines.append(f"  • #{item['number']}: [{item['title']}]({item['html_url']})")

                if failed:
                    text_lines.append(f"\n❌ *Failed ({len(failed)}):*")
                    for item in failed:
                        text_lines.append(f"  • {item['title']} - Error: {item['error']}")

                keyboard = [[InlineKeyboardButton("📊 View Board", callback_data="refresh_board")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await send_reply(update, context, "\n".join(text_lines), reply_markup=reply_markup, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error bulk parsing tasks: {e}")
            await send_reply(update, context, f"❌ *Error parsing draft tasks:* `{str(e)}`", parse_mode="Markdown")


async def task_prompt_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Intercepts text messages when awaiting user task title.
    Returns True if handled.
    """
    if not context.user_data.get("awaiting_task_title") or not update.message or not update.message.text:
        return False

    context.user_data.pop("awaiting_task_title", None)
    task_title = update.message.text.strip()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id

    await execute_create_single_task(update, context, user_id, chat_id, task_title)
    return True
