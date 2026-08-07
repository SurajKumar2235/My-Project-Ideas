import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot import api_client
from bot.commands.auth import ensure_authenticated
from bot.auth import admin_only
from bot.utils import send_reply, edit_reply

logger = logging.getLogger(__name__)

@admin_only
async def create_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/create-task [task_title]`.
    If task_title is provided, creates a single task.
    If no argument is provided, parses the user's latest draft for tasks and bulk creates them.
    """
    if not await ensure_authenticated(update, context):
        return

    if not update.effective_user or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # 1. Check if a specific task title was provided
    task_title_arg = " ".join(context.args) if context.args else ""
    
    if task_title_arg:
        loading_message = await send_reply(
            update, context,
            f"🔄 *Creating task:* `{task_title_arg}` on GitHub...",
            parse_mode="Markdown"
        )
        try:
            res = await api_client.create_task(user_id, chat_id, task_title_arg)
            issue_number = res.get("issue_number")
            html_url = res.get("html_url")
            repo = res.get("repo")
            
            await edit_reply(update, context, loading_message,
                f"✅ *Task Created Successfully!*\n\n"
                f"📌 *Task:* [#{issue_number}]({html_url}) - {task_title_arg}\n"
                f"📁 *Repository:* `{repo}`\n"
                f"📁 *Status:* `todo`\n\n"
                "Use `/board` to view active cards.",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.exception("Error creating single task:")
            await edit_reply(update, context, loading_message,
                f"❌ *Failed to create task.* \nError: `{str(e)}`",
                parse_mode="Markdown"
            )
        return

    # 2. Bulk creation from draft
    loading_message = await send_reply(
        update, context,
        "🔄 *Checking latest draft for checklist tasks...*",
        parse_mode="Markdown"
    )

    try:
        res = await api_client.create_task(user_id, chat_id, None)
        created = res.get("created", [])
        failed = res.get("failed", [])
        repo = res.get("repo", "Default Repo")
        message = res.get("message")

        if message:
            await edit_reply(update, context, loading_message, f"⚠️ {message}", parse_mode="Markdown")
            return

        # Construct the summary message
        summary_lines = [
            "📊 *Task Bulk Creation Summary*\n",
            f"📁 *Repository:* `{repo}`\n"
        ]
        
        if created:
            summary_lines.append(f"✅ *Created {len(created)} Tasks:*")
            for item in created:
                summary_lines.append(f"• [#{item['number']}]({item['html_url']}) - {item['title']}")
        
        if failed:
            if created:
                summary_lines.append("")
            summary_lines.append(f"❌ *Failed to Create {len(failed)} Tasks:*")
            for item in failed:
                summary_lines.append(f"• `{item['title']}` - {item['error']}")
                
        summary_lines.append("\nUse `/board` to manage and claim your new tasks.")
        
        await edit_reply(update, context, loading_message,
            "\n".join(summary_lines),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.exception("Error bulk creating tasks:")
        await edit_reply(update, context, loading_message,
            f"❌ *Failed to parse tasks.* \nError: `{str(e)}`",
            parse_mode="Markdown"
        )
