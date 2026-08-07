import logging
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import api_client
from bot.commands.auth import ensure_authenticated
from bot.auth import admin_only, is_user_admin
from bot.utils import send_reply, edit_reply

logger = logging.getLogger(__name__)

def sanitize_filename(title: str) -> str:
    cleaned = re.sub(r'[#\*\?\\\/\:\<\>\|\"]', '', title)
    cleaned = re.sub(r'\s+', '-', cleaned.strip())
    cleaned = cleaned.lower()
    cleaned = re.sub(r'[^a-z0-9\-]', '', cleaned)
    return cleaned if cleaned else "project-plan"


@admin_only
async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/plan <raw_idea>`.
    Generates a structured plan via the backend API, automatically saves it, and shows inline options.
    """
    if not await ensure_authenticated(update, context):
        return

    if not update.effective_user or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    idea_text = " ".join(context.args) if context.args else ""
    if not idea_text:
        await send_reply(
            update, context,
            "💡 Please provide a description of your idea after the command.\n\n"
            "Example:\n"
            "`/plan A simple telegram bot that links ideas to github issues`",
            parse_mode="Markdown"
        )
        return

    # Clear any previous feedback flags
    context.user_data["waiting_for_feedback"] = None

    try:
        loading_message = await send_reply(
            update, context,
            "🧠 *Formatting your idea with Groq... Please wait.*",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send initial loading message: {e}")
        await send_reply(update, context, f"❌ *Error:* `{str(e)}`", parse_mode="Markdown")
        return

    try:
        # Call backend to generate plan draft content (automatically saved in backend)
        resp = await api_client.generate_plan(user_id, chat_id, idea_text)
        formatted_markdown = resp["content"]
        repo_name = resp["repo"]
        draft_id = resp["draft_id"]
        
        # Store in user_data
        context.user_data["raw_idea"] = idea_text

        # Save local file
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

        keyboard = [
            [
                InlineKeyboardButton("💾 Save Draft", callback_data=f"save_draft:{draft_id}"),
                InlineKeyboardButton("🔄 Resend to AI", callback_data=f"resend_ai:{draft_id}"),
                InlineKeyboardButton("🚀 Push to GitHub", callback_data=f"push_draft:{draft_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        response_text = (
            f"✨ *Project Plan Draft Created!* (ID: `{draft_id}`)\n"
            f"📁 *Target Repository:* `{repo_name}`\n"
            f"📂 *Saved locally to:* `{filename}`\n\n"
            "✏️ *To edit manually:* Copy the markdown below, modify it, and send:\n"
            f"`/edit {draft_id} <modified_markdown>`\n\n"
            "```markdown\n"
            f"{formatted_markdown[:3000]}\n"
            "```"
        )
        
        await edit_reply(update, context, loading_message, response_text, reply_markup=reply_markup, parse_mode="Markdown")
        
    except Exception as e:
        logger.exception("Error while formatting plan:")
        if loading_message:
            await edit_reply(update, context, loading_message, 
                f"❌ *Failed to format plan.* \nError: `{str(e)}`",
                parse_mode="Markdown"
            )
        else:
            logger.error("Could not edit loading_message because it's None")


@admin_only
async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/edit <draft_id> <modified_markdown>`.
    Manually edits the content of a project plan draft.
    """
    if not await ensure_authenticated(update, context):
        return

    if not update.effective_user or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if len(context.args) < 2:
        await send_reply(
            update, context,
            "✏️ *Usage:*\n`/edit <draft_id> <modified_markdown>`\n\n"
            "Example:\n"
            "`/edit 2 # My New Title\n"
            "## Proposed Solution\n"
            "This is a modified solution...`",
            parse_mode="Markdown"
        )
        return

    draft_id_str = context.args[0]
    try:
        draft_id = int(draft_id_str)
    except ValueError:
        await send_reply(update, context, "❌ *Invalid Draft ID. Must be an integer.*", parse_mode="Markdown")
        return

    # Extract the markdown content from the full message text
    message_text = update.message.text
    first_space = message_text.find(" ")
    if first_space == -1:
        await send_reply(update, context, "❌ *Error parsing command.*", parse_mode="Markdown")
        return
    remainder = message_text[first_space:].strip()
    second_space = remainder.find(" ")
    if second_space == -1:
        await send_reply(update, context, "❌ *Please provide the new markdown content.*", parse_mode="Markdown")
        return
    new_content = remainder[second_space:].strip()

    loading_message = await send_reply(update, context, "💾 *Saving changes...*", parse_mode="Markdown")

    try:
        resp = await api_client.update_draft(user_id, chat_id, draft_id, new_content)
        repo_name = resp.get("repo", "Default Repo")

        # Save local file
        lines = new_content.strip().split("\n")
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
            f.write(new_content)

        response_text = (
            f"✅ *Draft {draft_id} Updated Successfully!*\n"
            f"📁 *Repository:* `{repo_name}`\n"
            f"📂 *Saved locally to:* `{filename}`\n\n"
            "✏️ *To edit manually:* Copy the markdown below, modify it, and send:\n"
            f"`/edit {draft_id} <modified_markdown>`\n\n"
            "```markdown\n"
            f"{new_content[:3000]}\n"
            "```"
        )

        keyboard = [
            [
                InlineKeyboardButton("💾 Save Draft", callback_data=f"save_draft:{draft_id}"),
                InlineKeyboardButton("🔄 Resend to AI", callback_data=f"resend_ai:{draft_id}"),
                InlineKeyboardButton("🚀 Push to GitHub", callback_data=f"push_draft:{draft_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await edit_reply(update, context, loading_message, response_text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.exception("Error updating draft:")
        await edit_reply(update, context, loading_message, f"❌ *Failed to update draft:* `{str(e)}`", parse_mode="Markdown")


async def save_draft_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the callback query when user clicks "Save Draft".
    """
    query = update.callback_query
    data = query.data

    if not data.startswith("save_draft:"):
        return

    if not await is_user_admin(update, context):
        await query.answer("⛔ Access Denied: Only administrators can save drafts.", show_alert=True)
        return

    if not update.effective_user or not update.effective_chat:
        return

    draft_id = int(data.split(":")[1])
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    try:
        drafts = await api_client.list_drafts(user_id, chat_id)
        target_draft = next((d for d in drafts if d["id"] == draft_id), None)
        
        if not target_draft:
            await query.answer("❌ Draft not found in database.", show_alert=True)
            return

        content = target_draft["content"]
        lines = content.strip().split("\n")
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
            f.write(content)

        await query.answer(f"💾 Draft #{draft_id} saved as {filename}!", show_alert=True)
    except Exception as e:
        logger.exception("Error saving draft:")
        await query.answer(f"❌ Failed to save draft: {str(e)}", show_alert=True)


async def plan_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the callback query when user clicks "Resend to AI".
    """
    query = update.callback_query
    data = query.data

    if not data.startswith("resend_ai:"):
        return

    if not await is_user_admin(update, context):
        await query.answer("⛔ Access Denied: Only administrators can refine plans.", show_alert=True)
        return

    await query.answer()

    draft_id = int(data.split(":")[1])
    context.user_data["waiting_for_feedback"] = draft_id
    
    # Send a new message so the original markdown remains visible for copying
    await query.message.reply_text(
        f"✍️ *Please type and send your feedback to refine Draft {draft_id}.*\n\n"
        "For example: 'Add FastAPI to the tech stack' or 'Add a testing section'.",
        parse_mode="Markdown"
    )


async def plan_feedback_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles text messages containing feedback when waiting_for_feedback contains a draft ID.
    """
    draft_id = context.user_data.get("waiting_for_feedback")
    if not draft_id:
        return

    # Reset wait state
    context.user_data["waiting_for_feedback"] = None

    if not update.effective_user or not update.effective_chat:
        return

    feedback_text = update.message.text
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    raw_idea = context.user_data.get("raw_idea", "Refine the existing project plan.")

    loading_message = await send_reply(
        update, context,
        "🔄 *Refining the project plan with your feedback... Please wait.*",
        parse_mode="Markdown"
    )

    try:
        # Retrieve previous markdown content if available
        drafts = await api_client.list_drafts(user_id, chat_id)
        previous_draft = next((d for d in drafts if d["id"] == draft_id), None)
        previous_markdown = previous_draft["content"] if previous_draft else None

        # Call backend to regenerate plan with previous context & feedback
        resp = await api_client.generate_plan(
            telegram_id=user_id,
            chat_id=chat_id,
            raw_idea=raw_idea,
            draft_id=draft_id,
            previous_markdown=previous_markdown,
            feedback=feedback_text
        )
        
        formatted_markdown = resp["content"]
        repo_name = resp["repo"]

        # Save local file
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

        keyboard = [
            [
                InlineKeyboardButton("💾 Save Draft", callback_data=f"save_draft:{draft_id}"),
                InlineKeyboardButton("🔄 Resend to AI", callback_data=f"resend_ai:{draft_id}"),
                InlineKeyboardButton("🚀 Push to GitHub", callback_data=f"push_draft:{draft_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        response_text = (
            f"✨ *Project Plan Refined!* (ID: `{draft_id}`)\n"
            f"📁 *Target Repository:* `{repo_name}`\n"
            f"📂 *Saved locally to:* `{filename}`\n\n"
            "✏️ *To edit manually:* Copy the markdown below, modify it, and send:\n"
            f"`/edit {draft_id} <modified_markdown>`\n\n"
            "```markdown\n"
            f"{formatted_markdown[:3000]}\n"
            "```"
        )

        await edit_reply(update, context, loading_message, response_text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.exception("Error refining plan:")
        await edit_reply(update, context, loading_message,
            f"❌ *Failed to refine plan.* \nError: `{str(e)}`",
            parse_mode="Markdown"
        )
