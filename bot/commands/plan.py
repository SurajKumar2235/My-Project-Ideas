import logging
import os
import re
from telegram import Update
from telegram.ext import ContextTypes
from bot import db, groq_client
from bot.auth import admin_only

logger = logging.getLogger(__name__)

def sanitize_filename(title: str) -> str:
    # Remove markdown headers and special characters
    cleaned = re.sub(r'[#\*\?\\\/\:\<\>\|\"]', '', title)
    # Convert spaces/tabs to dashes, remove extra dashes
    cleaned = re.sub(r'\s+', '-', cleaned.strip())
    # Convert to lowercase
    cleaned = cleaned.lower()
    # Keep only alphanumeric and dashes
    cleaned = re.sub(r'[^a-z0-9\-]', '', cleaned)
    # Avoid empty filename
    return cleaned if cleaned else "project-plan"

@admin_only
async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    """
    Handles `/plan <raw_idea>`.
    Formats the idea via Groq and saves it to the drafts table.
    """
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Extract the argument (the raw idea)
    idea_text = " ".join(context.args) if context.args else ""
    
    if not idea_text:
        await update.message.reply_text(
            "💡 Please provide a description of your idea after the command.\n\n"
            "Example:\n"
            "`/plan A simple telegram bot that links ideas to github issues`",
            parse_mode="Markdown"
        )
        return

    # Send a placeholder loading message
    loading_message = await update.message.reply_text(
        "🧠 *Formatting your idea with Groq... Please wait.*",
        parse_mode="Markdown"
    )

    try:
        # Call Groq to format the idea
        formatted_markdown = await groq_client.format_idea_to_markdown(idea_text, use_reasoning=True)
        
        # Save to database drafts
        db.save_draft(chat_id, user_id, formatted_markdown)
        
        # Extract title and write to local file
        lines = formatted_markdown.strip().split("\n")
        first_line = lines[0] if lines else "Project Plan"
        title = first_line.lstrip("#").strip()
        filename = f"{sanitize_filename(title)}.md"
        
        plans_dir = os.environ.get("PLANS_DIR", "")
        if plans_dir:
            os.makedirs(plans_dir, exist_ok=True)
            filepath = os.path.join(plans_dir, filename)
        else:
            filepath = filename
            
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(formatted_markdown)
            
        # Reply to the user with the formatted plan
        response_text = (
            "✨ *Project Plan Formatted!*\n"
            f"📂 Saved locally to: `{filename}`\n"
            "📝 Saved to your drafts. Use `/push` to create a GitHub issue for it.\n\n"
            "```markdown\n"
            f"{formatted_markdown}\n"
            "```"
        )
        
        await loading_message.edit_text(response_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.exception("Error while formatting plan:")
        await loading_message.edit_text(
            f"❌ *Failed to format plan.* \nError: `{str(e)}`",
            parse_mode="Markdown"
        )

