import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from bot import db, github_client

from bot.auth import admin_only

logger = logging.getLogger(__name__)

def parse_tasks_from_markdown(markdown_content: str) -> list[str]:
    """
    Parses all checklist tasks (lines starting with - [ ], * [ ], or + [ ])
    from a markdown plan.
    """
    pattern = r'^\s*[-*+]\s*\[\s*\]\s*(.+)$'
    tasks = []
    for line in markdown_content.splitlines():
        match = re.match(pattern, line)
        if match:
            task_title = match.group(1).strip()
            # Avoid matching parent phases if they have empty brackets or subtasks
            if task_title:
                tasks.append(task_title)
    return tasks

@admin_only
async def create_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/create-task [task_title]`.
    If task_title is provided, creates a single task.
    If no argument is provided, parses the user's latest draft for tasks and bulk creates them.
    """
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # 1. Check if a specific task title was provided by the user
    task_title_arg = " ".join(context.args) if context.args else ""
    
    if task_title_arg:
        # Create a single task
        loading_message = await update.message.reply_text(
            f"🔄 *Creating task:* `{task_title_arg}` on GitHub...",
            parse_mode="Markdown"
        )
        try:
            issue = await github_client.create_github_issue(
                title=task_title_arg,
                body="Created manually via bot command."
            )
            issue_number = issue.get("number")
            html_url = issue.get("html_url")
            
            # Save lock in SQLite
            db.save_lock(db.Lock(
                issue_number=issue_number,
                repo=github_client.GITHUB_PROJECT,
                status="todo"
            ))
            
            await loading_message.edit_text(
                f"✅ *Task Created Successfully!*\n\n"
                f"📌 **Task:** [#{issue_number}]({html_url}) - {task_title_arg}\n"
                f"📁 **Status:** `todo`\n\n"
                "Use `/board` to view active cards.",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.exception("Error creating single task:")
            await loading_message.edit_text(
                f"❌ *Failed to create task.* \nError: `{str(e)}`",
                parse_mode="Markdown"
            )
        return

    # 2. Bulk create tasks from latest draft
    draft = db.get_latest_draft(chat_id, user_id)
    if not draft:
        await update.message.reply_text(
            "📝 *No drafts found to parse tasks from.*\n"
            "Use `/plan <idea>` to generate a plan draft first, or provide a task title directly:\n"
            "Example: `/create-task Setup the database routing`",
            parse_mode="Markdown"
        )
        return

    # Parse checklist tasks
    tasks = parse_tasks_from_markdown(draft.content)
    if not tasks:
        await update.message.reply_text(
            "⚠️ *No actionable task items found in the draft.*\n"
            "Ensure the plan has checklists like `- [ ] Task Description`.",
            parse_mode="Markdown"
        )
        return

    loading_message = await update.message.reply_text(
        f"🔄 *Found {len(tasks)} tasks in the draft. Creating issues on GitHub...*",
        parse_mode="Markdown"
    )

    created_issues = []
    failed_tasks = []

    for task in tasks:
        try:
            # Create issue on GitHub
            issue = await github_client.create_github_issue(
                title=task,
                body=f"Created automatically from draft project plan.\nDraft Title: {draft.content.splitlines()[0]}"
            )
            issue_number = issue.get("number")
            html_url = issue.get("html_url")
            
            # Register lock in database
            db.save_lock(db.Lock(
                issue_number=issue_number,
                repo=github_client.GITHUB_PROJECT,
                status="todo"
            ))
            
            created_issues.append((issue_number, html_url, task))
        except Exception as e:
            logger.error(f"Failed to create task issue for '{task}': {e}")
            failed_tasks.append((task, str(e)))

    # Construct the summary message
    summary_lines = ["📊 *Task Bulk Creation Summary*\n"]
    
    if created_issues:
        summary_lines.append(f"✅ *Created {len(created_issues)} Tasks:*")
        for num, url, title in created_issues:
            summary_lines.append(f"• [#{num}]({url}) - {title}")
    
    if failed_tasks:
        if created_issues:
            summary_lines.append("")
        summary_lines.append(f"❌ *Failed to Create {len(failed_tasks)} Tasks:*")
        for title, err in failed_tasks:
            summary_lines.append(f"• `{title}` - {err}")
            
    summary_lines.append("\nUse `/board` to manage and claim your new tasks.")
    
    await loading_message.edit_text(
        "\n".join(summary_lines),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
