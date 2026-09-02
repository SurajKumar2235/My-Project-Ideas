import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot_v2 import api_client
from bot_v2.utils import send_reply, edit_reply
from bot_v2.commands.auth import ensure_authenticated

logger = logging.getLogger(__name__)

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/plan <raw_idea>`.
    Drafts and structures a project specification using LLM reasoning.
    """
    if not await ensure_authenticated(update, context):
        return

    raw_idea = " ".join(context.args) if context.args else ""
    if not raw_idea.strip():
        await send_reply(
            update, context,
            "💡 *Project Plan Generator*\n\n"
            "Please provide an idea to draft a project plan.\n\n"
            "**Usage:** `/plan Build an AI-powered automated task manager bot`",
            parse_mode="Markdown"
        )
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id

    loading_msg = await send_reply(
        update, context,
        "🧠 *Analyzing idea & generating project spec with AI reasoning...*\n_Please wait a moment..._",
        parse_mode="Markdown"
    )

    try:
        res = await api_client.generate_plan(user_id, chat_id, raw_idea)
        draft_id = res.get("draft_id")
        content = res.get("content", "")
        repo = res.get("repo", "Default Repo")

        msg_text = (
            f"📋 *Project Spec Draft generated!* (Draft ID: `{draft_id}`)\n"
            f"📁 *Target Repo:* `{repo}`\n\n"
            f"{content}\n\n"
            "---"
        )

        keyboard = [
            [
                InlineKeyboardButton("💾 Save Draft", callback_data=f"save_draft:{draft_id}"),
                InlineKeyboardButton("✏️ Refine Plan", callback_data=f"resend_ai:{draft_id}")
            ],
            [
                InlineKeyboardButton("🚀 Push Issue", callback_data=f"push_draft:{draft_id}"),
                InlineKeyboardButton("➕ Create Task", callback_data="prompt_create_task")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await edit_reply(update, context, loading_msg, msg_text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error generating plan: {e}")
        await edit_reply(update, context, loading_msg, f"❌ *Error generating plan:* `{str(e)}`", parse_mode="Markdown")


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/edit <feedback>`.
    Refines the latest generated draft using AI reasoning with user feedback.
    """
    if not await ensure_authenticated(update, context):
        return

    feedback = " ".join(context.args) if context.args else ""
    if not feedback.strip():
        await send_reply(
            update, context,
            "✏️ *Refine Project Plan*\n\n"
            "Provide instructions or feedback to refine your latest project draft.\n\n"
            "**Usage:** `/edit Add a section for Docker setup and PostgreSQL configuration`",
            parse_mode="Markdown"
        )
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id

    # Retrieve existing drafts
    drafts = await api_client.list_drafts(user_id, chat_id)
    if not drafts:
        await send_reply(
            update, context,
            "⚠️ *No Draft Found*\n\n"
            "No active project draft found to edit. Please create a plan first using `/plan <idea>`.",
            parse_mode="Markdown"
        )
        return

    latest_draft = drafts[-1]
    draft_id = latest_draft["id"]

    loading_msg = await send_reply(
        update, context,
        f"🔄 *Refining draft #{draft_id} with AI feedback...*\n_Please wait..._",
        parse_mode="Markdown"
    )

    try:
        res = await api_client.generate_plan(
            telegram_id=user_id,
            chat_id=chat_id,
            raw_idea="Refine the project specification based on feedback.",
            draft_id=draft_id,
            feedback=feedback
        )

        content = res.get("content", "")
        repo = res.get("repo", "Default Repo")

        msg_text = (
            f"✨ *Refined Project Spec!* (Draft ID: `{draft_id}`)\n"
            f"📁 *Target Repo:* `{repo}`\n\n"
            f"{content}\n\n"
            "---"
        )

        keyboard = [
            [
                InlineKeyboardButton("💾 Save Draft", callback_data=f"save_draft:{draft_id}"),
                InlineKeyboardButton("✏️ Refine Again", callback_data=f"resend_ai:{draft_id}")
            ],
            [
                InlineKeyboardButton("🚀 Push Issue", callback_data=f"push_draft:{draft_id}"),
                InlineKeyboardButton("➕ Create Task", callback_data="prompt_create_task")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await edit_reply(update, context, loading_msg, msg_text, reply_markup=reply_markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error editing plan: {e}")
        await edit_reply(update, context, loading_msg, f"❌ *Error refining plan:* `{str(e)}`", parse_mode="Markdown")


async def plan_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles plan button actions like `resend_ai:<draft_id>`.
    """
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("resend_ai:"):
        return

    await query.answer("Preparing refinement prompt...")
    draft_id = int(query.data.split("resend_ai:")[1])
    context.user_data["refining_draft_id"] = draft_id

    await send_reply(
        update, context,
        f"✏️ *Send your feedback for draft #{draft_id}:*\n\n"
        "Reply directly to this message with what you'd like to add or change.\n"
        "*(Or send `/edit <your feedback>`)*",
        parse_mode="Markdown"
    )


async def save_draft_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `save_draft:<draft_id>` inline button.
    """
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("save_draft:"):
        return

    draft_id = query.data.split("save_draft:")[1]
    await query.answer(f"✅ Draft #{draft_id} saved!", show_alert=True)
    await send_reply(
        update, context,
        f"💾 *Draft #{draft_id} Saved!*\n\nYour project spec draft has been saved to your workspace session.",
        parse_mode="Markdown"
    )


async def plan_feedback_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handles freeform text messages when a user is in plan refinement state.
    Returns True if handled.
    """
    refining_draft_id = context.user_data.get("refining_draft_id")
    if not refining_draft_id or not update.message or not update.message.text:
        return False

    # Clear refining state
    context.user_data.pop("refining_draft_id", None)
    feedback = update.message.text.strip()
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id

    loading_msg = await send_reply(
        update, context,
        f"🔄 *Applying feedback to draft #{refining_draft_id}...*\n_Refining with AI..._",
        parse_mode="Markdown"
    )

    try:
        res = await api_client.generate_plan(
            telegram_id=user_id,
            chat_id=chat_id,
            raw_idea="Refine draft",
            draft_id=refining_draft_id,
            feedback=feedback
        )

        content = res.get("content", "")
        repo = res.get("repo", "Default Repo")

        msg_text = (
            f"✨ *Refined Project Spec!* (Draft ID: `{refining_draft_id}`)\n"
            f"📁 *Target Repo:* `{repo}`\n\n"
            f"{content}\n\n"
            "---"
        )

        keyboard = [
            [
                InlineKeyboardButton("💾 Save Draft", callback_data=f"save_draft:{refining_draft_id}"),
                InlineKeyboardButton("✏️ Refine Again", callback_data=f"resend_ai:{refining_draft_id}")
            ],
            [
                InlineKeyboardButton("🚀 Push Issue", callback_data=f"push_draft:{refining_draft_id}"),
                InlineKeyboardButton("➕ Create Task", callback_data="prompt_create_task")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await edit_reply(update, context, loading_msg, msg_text, reply_markup=reply_markup, parse_mode="Markdown")
        return True

    except Exception as e:
        logger.error(f"Error applying plan feedback: {e}")
        await edit_reply(update, context, loading_msg, f"❌ *Error refining plan:* `{str(e)}`", parse_mode="Markdown")
        return True
