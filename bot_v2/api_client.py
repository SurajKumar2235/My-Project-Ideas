import os
import logging
import httpx
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Backend API Configuration
BACKEND_URL = (
    os.environ.get("BACKEND_URL") or
    os.environ.get("BASE_URL") or
    os.environ.get("WEBSITE_URL") or
    "http://localhost:8000"
).rstrip("/")
BOT_API_SECRET = os.environ.get("BOT_API_SECRET", "dev-bot-secret")

def get_headers() -> Dict[str, str]:
    return {
        "X-Bot-Token": BOT_API_SECRET,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

async def _post(endpoint: str, payload: dict) -> dict:
    url = f"{BACKEND_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(url, headers=get_headers(), json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error on {endpoint}: {e.response.text}")
            try:
                error_detail = e.response.json().get("detail", str(e))
            except Exception:
                error_detail = e.response.text or str(e)
            raise Exception(error_detail)
        except Exception as e:
            logger.error(f"Connection error on {endpoint}: {e}")
            raise Exception(f"Failed to connect to backend server: {str(e)}")

async def identify_user(telegram_id: int) -> dict:
    """Checks if Telegram user is registered, authenticated, and gets role/allowed_commands."""
    return await _post("/api/bot/identify", {"telegram_id": telegram_id})

async def logout_user(telegram_id: int) -> dict:
    """Disassociates GitHub account for the Telegram user."""
    return await _post("/api/bot/logout", {"telegram_id": telegram_id})

async def get_login_link(telegram_id: int, chat_id: int) -> str:
    """Generates the unique OAuth login URL for the Telegram user."""
    data = await _post("/api/bot/login-link", {"telegram_id": telegram_id, "chat_id": chat_id})
    return data["login_url"]

async def list_user_repos(telegram_id: int) -> List[str]:
    """Lists write-accessible GitHub repositories for the Telegram user."""
    data = await _post("/api/bot/repos", {"telegram_id": telegram_id})
    return data.get("repos", [])

async def select_repo(telegram_id: int, repo: str) -> dict:
    """Sets active repository for the Telegram user."""
    return await _post("/api/bot/select_repo", {"telegram_id": telegram_id, "repo": repo})

async def generate_plan(
    telegram_id: int,
    chat_id: int,
    raw_idea: str,
    draft_id: Optional[int] = None,
    previous_markdown: Optional[str] = None,
    feedback: Optional[str] = None
) -> dict:
    """Invokes LLM plan generation or refinement."""
    payload = {
        "telegram_id": telegram_id,
        "chat_id": chat_id,
        "raw_idea": raw_idea,
        "draft_id": draft_id,
        "previous_markdown": previous_markdown,
        "feedback": feedback
    }
    return await _post("/api/bot/plan", payload)

async def create_draft(telegram_id: int, chat_id: int, content: str) -> dict:
    """Saves a draft directly in the backend."""
    return await _post("/api/bot/drafts/create", {
        "telegram_id": telegram_id,
        "chat_id": chat_id,
        "content": content
    })

async def update_draft(telegram_id: int, chat_id: int, draft_id: int, content: str) -> dict:
    """Updates a draft directly in the backend."""
    return await _post("/api/bot/drafts/update", {
        "telegram_id": telegram_id,
        "chat_id": chat_id,
        "draft_id": draft_id,
        "content": content
    })

async def list_drafts(telegram_id: int, chat_id: int) -> List[dict]:
    """Lists saved drafts for the Telegram user and chat."""
    data = await _post("/api/bot/drafts/list", {"telegram_id": telegram_id, "chat_id": chat_id})
    return data.get("drafts", [])

async def push_draft(telegram_id: int, chat_id: int, draft_id: Optional[int] = None) -> dict:
    """Pushes a saved draft as a GitHub issue."""
    return await _post("/api/bot/push", {"telegram_id": telegram_id, "chat_id": chat_id, "draft_id": draft_id})

async def create_task(telegram_id: int, chat_id: int, task_title: Optional[str] = None) -> dict:
    """Creates a single task or bulk-creates tasks parsed from draft checkboxes."""
    return await _post("/api/bot/create_task", {"telegram_id": telegram_id, "chat_id": chat_id, "task_title": task_title})

async def get_board(telegram_id: int) -> dict:
    """Retrieves Kanban Board columns for active repository."""
    return await _post("/api/bot/board", {"telegram_id": telegram_id})

async def claim_card(telegram_id: int, username: str, issue_number: int, repo: str) -> str:
    """Claims a Kanban task card."""
    data = await _post("/api/bot/board/claim", {
        "telegram_id": telegram_id,
        "username": username,
        "issue_number": issue_number,
        "repo": repo
    })
    return data.get("result", "failed")

async def release_card(telegram_id: int, issue_number: int, repo: str, is_admin: bool = False) -> str:
    """Releases a claimed task card back to TODO."""
    data = await _post("/api/bot/board/release", {
        "telegram_id": telegram_id,
        "issue_number": issue_number,
        "repo": repo,
        "is_admin": is_admin
    })
    return data.get("result", "failed")

async def mark_card_done(telegram_id: int, issue_number: int, repo: str) -> str:
    """Marks a claimed task card completed (DONE)."""
    data = await _post("/api/bot/board/done", {
        "telegram_id": telegram_id,
        "issue_number": issue_number,
        "repo": repo
    })
    return data.get("result", "failed")

# --- Admin API Calls ---

async def list_admin_users(admin_telegram_id: int) -> List[dict]:
    """Lists all registered users in the database for admins."""
    data = await _post("/api/bot/admin/users", {"admin_telegram_id": admin_telegram_id})
    return data.get("users", [])

async def set_user_role(admin_telegram_id: int, target_telegram_id: int, role: str) -> dict:
    """Sets a user's role (superadmin, admin, user)."""
    return await _post("/api/bot/admin/set_role", {
        "admin_telegram_id": admin_telegram_id,
        "target_telegram_id": target_telegram_id,
        "role": role
    })

async def set_user_commands(admin_telegram_id: int, target_telegram_id: int, allowed_commands: Optional[List[str]]) -> dict:
    """Sets allowed commands list for a user."""
    return await _post("/api/bot/admin/set_commands", {
        "admin_telegram_id": admin_telegram_id,
        "target_telegram_id": target_telegram_id,
        "allowed_commands": allowed_commands
    })
