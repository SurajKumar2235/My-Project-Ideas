import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot_v2 import api_client
from bot_v2.utils import send_reply

logger = logging.getLogger(__name__)


async def admin_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/users` or `/admin_users`.
    Lists all registered bot users, their roles, active repos, and allowed commands.
    Restricted to superadmins and admins.
    """
    if not update.effective_user:
        return

    admin_id = update.effective_user.id
    try:
        users = await api_client.list_admin_users(admin_id)
        if not users:
            await send_reply(update, context, "ℹ️ *No registered users found in database.*", parse_mode="Markdown")
            return

        text_lines = [
            "👥 *Registered Bot Users & Permissions*\n"
        ]

        for u in users:
            tg_id = u.get("telegram_id") or "Unlinked"
            username = u.get("username") or "Unknown"
            role = u.get("role", "user")
            active_repo = u.get("active_repo") or "None"
            allowed_cmds = u.get("allowed_commands")
            
            cmd_str = "All Commands" if not allowed_cmds or "*" in allowed_cmds else ", ".join(allowed_cmds)

            role_badge = "👑 SUPERADMIN" if role == "superadmin" else ("🛡 ADMIN" if role == "admin" else "👤 USER")

            text_lines.append(
                f"• *{username}* (ID: `{tg_id}`)\n"
                f"  Role: {role_badge}\n"
                f"  Repo: `{active_repo}`\n"
                f"  Allowed Commands: `{cmd_str}`\n"
            )

        await send_reply(update, context, "\n".join(text_lines), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in admin users command: {e}")
        await send_reply(update, context, f"❌ *Admin Error:* `{str(e)}`", parse_mode="Markdown")


async def set_role_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/set_role <target_telegram_id> <user|admin|superadmin>`.
    Updates a user's role in the database.
    Restricted to superadmins and admins.
    """
    if not update.effective_user:
        return

    admin_id = update.effective_user.id
    args = context.args or []

    if len(args) < 2:
        await send_reply(
            update, context,
            "🛡 *Set User Role*\n\n"
            "**Usage:** `/set_role <target_telegram_id> <user|admin|superadmin>`\n"
            "**Example:** `/set_role 939251900 admin`",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(args[0])
        new_role = args[1].lower().strip()

        if new_role not in ("user", "admin", "superadmin"):
            await send_reply(update, context, "❌ *Invalid role.* Role must be `user`, `admin`, or `superadmin`.", parse_mode="Markdown")
            return

        res = await api_client.set_user_role(admin_id, target_id, new_role)
        await send_reply(
            update, context,
            f"✅ *Role Updated Successfully!*\n\n"
            f"User ID `{target_id}` role has been updated to `{new_role}`.",
            parse_mode="Markdown"
        )
    except ValueError:
        await send_reply(update, context, "❌ *Invalid Telegram ID.* Please specify a numeric Telegram ID.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in set_role command: {e}")
        await send_reply(update, context, f"❌ *Admin Error:* `{str(e)}`", parse_mode="Markdown")


async def set_command_permissions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles `/set_command <target_telegram_id> <command1,command2|all|none>`.
    Sets allowed command permissions for a specific user.
    Restricted to superadmins and admins.
    """
    if not update.effective_user:
        return

    admin_id = update.effective_user.id
    args = context.args or []

    if len(args) < 2:
        await send_reply(
            update, context,
            "🔐 *Set Command Permissions*\n\n"
            "**Usage:** `/set_command <target_telegram_id> <command1,command2...|all|none>`\n\n"
            "**Examples:**\n"
            "• `/set_command 939251900 login,repo,board,plan` (Restrict to specific commands)\n"
            "• `/set_command 939251900 all` (Grant access to all commands)\n"
            "• `/set_command 939251900 none` (Revoke all commands)",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(args[0])
        cmd_input = args[1].lower().strip()

        if cmd_input == "all" or cmd_input == "*":
            allowed_cmds = None  # None indicates all standard commands allowed
            disp_str = "All Commands Allowed"
        elif cmd_input == "none":
            allowed_cmds = []
            disp_str = "No Commands Allowed"
        else:
            allowed_cmds = [c.strip().lstrip("/") for c in cmd_input.split(",") if c.strip()]
            disp_str = ", ".join(allowed_cmds)

        res = await api_client.set_user_commands(admin_id, target_id, allowed_cmds)
        await send_reply(
            update, context,
            f"✅ *Command Permissions Updated!*\n\n"
            f"User ID `{target_id}` allowed commands: `{disp_str}`",
            parse_mode="Markdown"
        )
    except ValueError:
        await send_reply(update, context, "❌ *Invalid Telegram ID.* Please specify a numeric Telegram ID.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in set_command command: {e}")
        await send_reply(update, context, f"❌ *Admin Error:* `{str(e)}`", parse_mode="Markdown")
