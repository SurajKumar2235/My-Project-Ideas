import os
import logging
import httpx
import re
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Header, Body
from pydantic import BaseModel
from datetime import datetime, timezone
from core.models import User, Draft, Lock
from client import groq_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bot", tags=["Telegram Bot API"])

# Security Dependency
async def verify_bot_token(x_bot_token: str = Header(...)):
    expected_token = os.environ.get("BOT_API_SECRET", "dev-bot-secret")
    if x_bot_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Bot API Secret Token."
        )

# Request / Response Schemas
class IdentifyRequest(BaseModel):
    telegram_id: int

class LoginLinkRequest(BaseModel):
    telegram_id: int
    chat_id: int

class SelectRepoRequest(BaseModel):
    telegram_id: int
    repo: str

class PlanRequest(BaseModel):
    telegram_id: int
    chat_id: int
    raw_idea: str
    draft_id: Optional[int] = None
    previous_markdown: Optional[str] = None
    feedback: Optional[str] = None

class CreateDraftRequest(BaseModel):
    telegram_id: int
    chat_id: int
    content: str

class UpdateDraftRequest(BaseModel):
    telegram_id: int
    chat_id: int
    draft_id: int
    content: str

class PushRequest(BaseModel):
    telegram_id: int
    chat_id: int
    draft_id: Optional[int] = None

class CreateTaskRequest(BaseModel):
    telegram_id: int
    chat_id: int
    task_title: Optional[str] = None

class ClaimCardRequest(BaseModel):
    telegram_id: int
    username: str
    issue_number: int
    repo: str

class ReleaseCardRequest(BaseModel):
    telegram_id: int
    issue_number: int
    repo: str
    is_admin: bool = False

class DoneCardRequest(BaseModel):
    telegram_id: int
    issue_number: int
    repo: str

class ListDraftsRequest(BaseModel):
    telegram_id: int
    chat_id: int

class AdminUsersRequest(BaseModel):
    admin_telegram_id: int

class SetRoleRequest(BaseModel):
    admin_telegram_id: int
    target_telegram_id: int
    role: str

class SetCommandsRequest(BaseModel):
    admin_telegram_id: int
    target_telegram_id: int
    allowed_commands: Optional[List[str]] = None


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    users = await User.filter(telegram_id=telegram_id).order_by("-id").all()
    if not users:
        return None
    primary_user = users[0]
    if len(users) > 1:
        for old_u in users[1:]:
            if not primary_user.access_token and old_u.access_token:
                primary_user.access_token = old_u.access_token
                if not primary_user.active_repo:
                    primary_user.active_repo = old_u.active_repo
                await primary_user.save()
            try:
                await old_u.delete()
            except Exception as e:
                logger.warning(f"Failed to delete duplicate user record {old_u.id}: {e}")
    return primary_user


@router.post("/drafts/list", summary="List Drafts for Telegram user")
async def list_drafts(body: ListDraftsRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    if not user:
        return {"drafts": []}
    drafts = await Draft.filter(user=user, chat_id=body.chat_id).all()
    return {
        "drafts": [
            {"id": d.id, "content": d.content, "repo": d.repo or "Default Repo"}
            for d in drafts
        ]
    }


# Helper to fetch active repository and token for user
async def get_user_github_context(user: User):
    token = user.access_token
    repo = user.active_repo
    is_fallback = False

    if not repo:
        # Fall back to public default repository config
        repo = os.environ.get("GITHUB_REPO", "")
        token = os.environ.get("GITHUB_TOKEN", "")
        is_fallback = True
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No repository configured. Set active repo or GITHUB_REPO env var."
            )
    return token, repo, is_fallback


@router.post("/identify", summary="Identify Telegram User Status")
async def identify_user(body: IdentifyRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    
    admin_ids_str = os.environ.get("ADMIN_USER_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

    if user and body.telegram_id in admin_ids and user.role not in ("admin", "superadmin"):
        user.role = "superadmin"
        await user.save()

    is_admin = (user and user.role in ("admin", "superadmin")) or (body.telegram_id in admin_ids)

    if not user:
        return {
            "authenticated": False,
            "is_admin": is_admin,
            "message": "User not registered in the system."
        }
    
    return {
        "authenticated": user.access_token is not None,
        "is_admin": is_admin,
        "user": {
            "id": user.id,
            "username": user.username,
            "github_id": user.github_id,
            "active_repo": user.active_repo,
            "role": user.role,
            "allowed_commands": user.allowed_commands
        }
    }


@router.post("/logout", summary="Logout and Disassociate GitHub Account")
async def logout_bot_user(body: IdentifyRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    if not user:
        return {
            "status": "success",
            "message": "User not registered or already logged out."
        }
    
    user.access_token = None
    user.active_repo = None
    user.github_id = None
    await user.save()
    
    return {
        "status": "success",
        "message": "GitHub account disassociated successfully."
    }


@router.post("/login-link", summary="Generate GitHub OAuth Redirection Link")
async def get_login_link(body: LoginLinkRequest, _ = Depends(verify_bot_token)):
    website_url = os.environ.get("WEBSITE_URL") or os.environ.get("BASE_URL") or "http://localhost:8000"
    state = f"telegram_{body.telegram_id}_{body.chat_id}"
    login_url = f"{website_url}/auth/github/login?state={state}"
    return {
        "login_url": login_url
    }


@router.post("/repos", summary="List Repositories for Telegram User")
async def list_bot_user_repos(body: IdentifyRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    token = (user.access_token if user else None) or os.environ.get("GITHUB_TOKEN", "")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated. Link GitHub account first."
        )

    url = "https://api.github.com/user/repos"
    params = {"sort": "updated", "per_page": 20}
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            # Fall back to default repo if user repos call fails
            default_repo = os.environ.get("GITHUB_REPO", "")
            return {"status": "success", "repos": [default_repo] if default_repo else []}

        repos = resp.json()
        result = []
        for r in repos:
            perms = r.get("permissions", {})
            if perms.get("push", False) or perms.get("admin", False) or perms.get("pull", True):
                result.append(r.get("full_name"))
        return {
            "status": "success",
            "repos": result
        }


@router.post("/select_repo", summary="Select Active Repository for Telegram User")
async def select_bot_user_repo(body: SelectRepoRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not registered. Please link your GitHub account using /login."
        )

    repo_name = body.repo.strip()
    token = user.access_token or os.environ.get("GITHUB_TOKEN", "")

    if token:
        url = f"https://api.github.com/repos/{repo_name}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                repo_data = resp.json()
                perms = repo_data.get("permissions", {})
                if perms and not (perms.get("push") or perms.get("admin") or perms.get("pull")):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You must have access to select this repository."
                    )

    user.active_repo = repo_name
    await user.save()

    return {
        "status": "success",
        "active_repo": repo_name,
        "username": user.username or "User"
    }


@router.post("/plan", summary="Generate/Refine Project Plan")
async def generate_plan_draft(body: PlanRequest, _ = Depends(verify_bot_token)):
    user = await User.get_or_none(telegram_id=body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated."
        )

    try:
        previous_markdown = body.previous_markdown
        if body.draft_id and not previous_markdown:
            existing_draft = await Draft.filter(id=body.draft_id, user=user).first()
            if existing_draft:
                previous_markdown = existing_draft.content

        # Call Groq to format the idea (supporting refinement feedback)
        formatted_markdown = await groq_client.format_idea_to_markdown(
            body.raw_idea or "Refine the project plan.",
            use_reasoning=True,
            previous_markdown=previous_markdown,
            feedback=body.feedback
        )

        if body.draft_id:
            # Update existing draft
            draft = await Draft.filter(id=body.draft_id, user=user).first()
            if draft:
                draft.content = formatted_markdown
                await draft.save()
            else:
                draft = await Draft.create(
                    user=user,
                    chat_id=body.chat_id,
                    content=formatted_markdown,
                    repo=user.active_repo
                )
        else:
            # Create new draft
            draft = await Draft.create(
                user=user,
                chat_id=body.chat_id,
                content=formatted_markdown,
                repo=user.active_repo
            )

        return {
            "status": "success",
            "draft_id": draft.id,
            "content": formatted_markdown,
            "repo": draft.repo or user.active_repo or "Default Repo"
        }
    except Exception as e:
        logger.exception("Error creating plan draft:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate project plan: {str(e)}"
        )


@router.post("/drafts/create", summary="Save draft directly")
async def create_draft_direct(body: CreateDraftRequest, _ = Depends(verify_bot_token)):
    user = await User.get_or_none(telegram_id=body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated."
        )

    draft = await Draft.create(
        user=user,
        chat_id=body.chat_id,
        content=body.content,
        repo=user.active_repo
    )

    return {
        "status": "success",
        "draft_id": draft.id,
        "repo": user.active_repo or "Default Repo"
    }


@router.post("/drafts/update", summary="Update draft content directly")
async def update_draft_content(body: UpdateDraftRequest, _ = Depends(verify_bot_token)):
    user = await User.get_or_none(telegram_id=body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated."
        )

    draft = await Draft.filter(id=body.draft_id, user=user).first()
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found."
        )

    draft.content = body.content
    await draft.save()

    return {
        "status": "success",
        "draft_id": draft.id,
        "repo": draft.repo or user.active_repo or "Default Repo"
    }


@router.post("/push", summary="Push Draft to GitHub Issue")
async def push_draft_to_github(body: PushRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated."
        )

    # 1. Retrieve draft
    if body.draft_id:
        draft = await Draft.filter(id=body.draft_id, user=user).first()
    else:
        draft = await Draft.filter(user=user, chat_id=body.chat_id).order_by("-created_at").first()

    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No project draft found."
        )

    # 2. Get repository context
    token, repo, is_fallback = await get_user_github_context(user)

    # 3. Create issue on GitHub
    content = draft.content.strip()
    lines = content.split("\n")
    title = lines[0].lstrip("#").strip() if lines else "Untitled Idea"
    body_text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "title": title,
        "body": body_text,
        "labels": ["status:todo"]
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 201:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub API Issue Creation Error: {resp.text}"
            )
        issue = resp.json()
        issue_number = issue.get("number")
        html_url = issue.get("html_url")

        # 4. Save Lock in database using Tortoise
        # Check if lock already exists (repo, issue_number)
        lock = await Lock.get_or_none(repo=repo, issue_number=issue_number)
        if not lock:
            await Lock.create(
                repo=repo,
                issue_number=issue_number,
                status="todo"
            )

        # 5. Delete draft
        await draft.delete()

        return {
            "status": "success",
            "issue_number": issue_number,
            "html_url": html_url,
            "title": title,
            "repo": repo
        }


def parse_tasks_from_markdown(markdown_content: str) -> list[str]:
    pattern = r'^\s*[-*+]\s*\[\s*\]\s*(.+)$'
    tasks = []
    for line in markdown_content.splitlines():
        match = re.match(pattern, line)
        if match:
            task_title = match.group(1).strip()
            if task_title:
                tasks.append(task_title)
    return tasks


@router.post("/create_task", summary="Create Single Task or Parse Draft tasks")
async def create_task(body: CreateTaskRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated."
        )

    token, repo, is_fallback = await get_user_github_context(user)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Case A: Single Task Creation
        if body.task_title:
            url = f"https://api.github.com/repos/{repo}/issues"
            payload = {
                "title": body.task_title,
                "body": "Created manually via bot command.",
                "labels": ["status:todo"]
            }
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 201:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"GitHub Issue Creation Error: {resp.text}"
                )
            issue = resp.json()
            issue_number = issue.get("number")
            html_url = issue.get("html_url")

            await Lock.get_or_create(repo=repo, issue_number=issue_number, defaults={"status": "todo"})

            return {
                "type": "single",
                "issue_number": issue_number,
                "html_url": html_url,
                "title": body.task_title,
                "repo": repo
            }

        # Case B: Bulk Create Tasks from Latest Draft
        draft = await Draft.filter(user=user, chat_id=body.chat_id).order_by("-created_at").first()
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pending draft found to parse tasks."
            )

        tasks = parse_tasks_from_markdown(draft.content)
        if not tasks:
            return {
                "type": "bulk",
                "created": [],
                "failed": [],
                "message": "No actionable checkboxes found in draft."
            }

        created = []
        failed = []

        url = f"https://api.github.com/repos/{repo}/issues"
        draft_title = draft.content.splitlines()[0]

        for task in tasks:
            payload = {
                "title": task,
                "body": f"Created automatically from draft project plan.\nDraft Title: {draft_title}",
                "labels": ["status:todo"]
            }
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 201:
                issue = resp.json()
                issue_number = issue.get("number")
                html_url = issue.get("html_url")
                
                await Lock.get_or_create(repo=repo, issue_number=issue_number, defaults={"status": "todo"})
                created.append({"number": issue_number, "html_url": html_url, "title": task})
            else:
                failed.append({"title": task, "error": resp.text})

        return {
            "type": "bulk",
            "created": created,
            "failed": failed,
            "repo": repo
        }


@router.post("/board", summary="Get Kanban Board for Telegram user")
async def get_bot_board(body: IdentifyRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated."
        )

    token, repo, is_fallback = await get_user_github_context(user)

    url = f"https://api.github.com/repos/{repo}/issues"
    params = {"state": "open", "per_page": 100}
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch issues from GitHub: {resp.text}"
            )
        gh_issues = resp.json()

    # Sync and get locks
    # Find all locks for this repository
    locks = await Lock.filter(repo=repo)
    locks_dict = {l.issue_number: l for l in locks}

    todo_list = []
    doing_list = []
    done_list = []

    for issue in gh_issues:
        # Ignore pull requests
        if "pull_request" in issue:
            continue

        issue_number = issue.get("number")
        title = issue.get("title")
        html_url = issue.get("html_url")

        # Sync lock in DB if not exists
        if issue_number not in locks_dict:
            lock = await Lock.create(
                repo=repo,
                issue_number=issue_number,
                status="todo"
            )
            locks_dict[issue_number] = lock
        
        lock = locks_dict[issue_number]
        status_name = lock.status
        assignee = lock.locked_by_username

        issue_info = {
            "number": issue_number,
            "title": title,
            "html_url": html_url,
            "assignee": assignee
        }

        if status_name == "doing":
            doing_list.append(issue_info)
        elif status_name == "done":
            done_list.append(issue_info)
        else:
            todo_list.append(issue_info)

    return {
        "repo": repo,
        "todo": todo_list,
        "doing": doing_list,
        "done": done_list
    }


# Helper for syncing issue updates to GitHub
async def sync_issue_state_to_github(issue_number: int, github_username: str | None, status_label: str, token: str, repo: str):
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Fetch current issue labels
        get_resp = await client.get(url, headers=headers)
        if get_resp.status_code != 200:
            logger.error(f"Failed to fetch issue #{issue_number} labels: {get_resp.text}")
            return
        
        issue_data = get_resp.json()
        current_labels = [label["name"] for label in issue_data.get("labels", [])]
        filtered_labels = [l for l in current_labels if not l.startswith("status:")]
        filtered_labels.append(status_label)

        # 2. Update issue
        payload = {"labels": filtered_labels}
        if github_username:
            payload["assignees"] = [github_username]
        else:
            payload["assignees"] = []

        patch_resp = await client.patch(url, headers=headers, json=payload)
        if patch_resp.status_code == 422 and github_username:
            # Fallback to labels only if username assign fails
            payload.pop("assignees", None)
            await client.patch(url, headers=headers, json=payload)


@router.post("/board/claim", summary="Claim a Kanban Card")
async def claim_board_card(body: ClaimCardRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated."
        )

    token, repo, _ = await get_user_github_context(user)

    # 1. Check current lock status
    lock = await Lock.get_or_none(repo=body.repo, issue_number=body.issue_number)
    if not lock:
        lock = await Lock.create(repo=body.repo, issue_number=body.issue_number, status="todo")

    if lock.status == "doing":
        if lock.locked_by_user_id == user.id:
            return {"result": "already_claimed_by_you"}
        else:
            return {"result": "already_claimed_by_other"}
    elif lock.status == "done":
        return {"result": "already_done"}

    # 2. Update Lock atomically
    lock.status = "doing"
    lock.locked_by_user = user
    lock.locked_by_username = body.username
    lock.locked_at = datetime.now(timezone.utc)
    await lock.save()

    # 3. Sync to GitHub
    try:
        # Get user's github username if possible, or fallback to body.username
        gh_username = user.username or body.username
        await sync_issue_state_to_github(body.issue_number, gh_username, "status:doing", token, body.repo)
    except Exception as e:
        logger.error(f"GitHub claim sync failed for issue #{body.issue_number}: {e}")

    return {"result": "claimed"}


@router.post("/board/release", summary="Release a claimed Kanban Card")
async def release_board_card(body: ReleaseCardRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated."
        )

    token, repo, _ = await get_user_github_context(user)

    lock = await Lock.get_or_none(repo=body.repo, issue_number=body.issue_number)
    if not lock or lock.status != "doing":
        return {"result": "not_claimed"}

    # Authorization Check (must be owner of lock or admin)
    # Fetch locked_by_user
    await lock.fetch_related("locked_by_user")
    if not body.is_admin and (not lock.locked_by_user or lock.locked_by_user.id != user.id):
        return {"result": "unauthorized"}

    # Release
    lock.status = "todo"
    lock.locked_by_user = None
    lock.locked_by_username = None
    lock.locked_at = None
    await lock.save()

    # Sync to GitHub
    try:
        await sync_issue_state_to_github(body.issue_number, None, "status:todo", token, body.repo)
    except Exception as e:
        logger.error(f"GitHub release sync failed: {e}")

    return {"result": "released"}


@router.post("/board/done", summary="Mark claimed Kanban Card Completed")
async def done_board_card(body: DoneCardRequest, _ = Depends(verify_bot_token)):
    user = await get_user_by_telegram_id(body.telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated."
        )

    token, repo, _ = await get_user_github_context(user)

    lock = await Lock.get_or_none(repo=body.repo, issue_number=body.issue_number)
    if not lock or lock.status != "doing":
        return {"result": "not_claimed"}

    await lock.fetch_related("locked_by_user")
    if not lock.locked_by_user or lock.locked_by_user.id != user.id:
        return {"result": "unauthorized"}

    # Complete
    lock.status = "done"
    await lock.save()

    # Sync to GitHub
    try:
        await sync_issue_state_to_github(body.issue_number, lock.locked_by_username, "status:done", token, body.repo)
    except Exception as e:
        logger.error(f"GitHub done sync failed: {e}")

    return {"result": "marked_done"}


# --- Admin Management Endpoints ---

async def verify_admin_access(telegram_id: int) -> User:
    admin_ids_str = os.environ.get("ADMIN_USER_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
    
    user = await User.get_or_none(telegram_id=telegram_id)
    is_admin = (user and user.role in ("admin", "superadmin")) or (telegram_id in admin_ids)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required."
        )
    return user


@router.post("/admin/users", summary="List All Registered Bot Users")
async def list_admin_users(body: AdminUsersRequest, _ = Depends(verify_bot_token)):
    await verify_admin_access(body.admin_telegram_id)
    users = await User.all()
    
    admin_ids_str = os.environ.get("ADMIN_USER_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

    result = []
    for u in users:
        role = u.role
        if u.telegram_id in admin_ids and role == "user":
            role = "superadmin"
        result.append({
            "id": u.id,
            "telegram_id": u.telegram_id,
            "username": u.username,
            "email": u.email,
            "role": role,
            "active_repo": u.active_repo,
            "allowed_commands": u.allowed_commands,
            "is_connected": u.access_token is not None
        })
    return {"status": "success", "users": result}


@router.post("/admin/set_role", summary="Set User Role")
async def set_user_role(body: SetRoleRequest, _ = Depends(verify_bot_token)):
    await verify_admin_access(body.admin_telegram_id)
    
    target_user = await User.get_or_none(telegram_id=body.target_telegram_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with Telegram ID {body.target_telegram_id} not found."
        )
    
    role = body.role.lower().strip()
    if role not in ("user", "admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be one of: user, admin, superadmin"
        )
    
    target_user.role = role
    await target_user.save()
    return {"status": "success", "telegram_id": body.target_telegram_id, "new_role": role}


@router.post("/admin/set_commands", summary="Set User Allowed Commands")
async def set_user_commands(body: SetCommandsRequest, _ = Depends(verify_bot_token)):
    await verify_admin_access(body.admin_telegram_id)
    
    target_user = await User.get_or_none(telegram_id=body.target_telegram_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with Telegram ID {body.target_telegram_id} not found."
        )
    
    target_user.allowed_commands = body.allowed_commands
    await target_user.save()
    return {
        "status": "success",
        "telegram_id": body.target_telegram_id,
        "allowed_commands": body.allowed_commands
    }
