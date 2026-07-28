import re
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bot import db, github_client
from bot.models import User
from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


class CreateTaskRequest(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    draft_id: Optional[int] = None
    chat_id: Optional[int] = None


def parse_tasks_from_markdown(markdown_content: str) -> List[str]:
    pattern = r'^\s*[-*+]\s*\[\s*\]\s*(.+)$'
    tasks = []
    for line in markdown_content.splitlines():
        match = re.match(pattern, line)
        if match:
            task_title = match.group(1).strip()
            if task_title:
                tasks.append(task_title)
    return tasks


@router.post("", summary="Create Single Task or Bulk Parse Tasks from Draft")
async def create_tasks(
    req: CreateTaskRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Creates tasks as GitHub issues.
    - If `title` is provided: Creates a single GitHub issue task.
    - If `title` is not provided: Parses task items (`- [ ] task`) from specified `draft_id` or user's latest draft and bulk-creates them.
    """
    user_id = current_user.id
    target_chat_id = req.chat_id if req.chat_id is not None else user_id

    # 1. Single task creation
    if req.title and req.title.strip():
        try:
            task_body = req.body if req.body else f"Created via API by {current_user.username}"
            issue = await github_client.create_github_issue(title=req.title.strip(), body=task_body)
            issue_number = issue.get("number")
            html_url = issue.get("html_url")

            db.save_lock(db.Lock(
                issue_number=issue_number,
                repo=github_client.GITHUB_PROJECT,
                status="todo"
            ))

            return {
                "status": "success",
                "message": "Task created successfully",
                "issue_number": issue_number,
                "html_url": html_url,
                "title": req.title.strip(),
                "issue_status": "todo"
            }
        except Exception as e:
            logger.exception("Error creating single task issue:")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create task issue: {str(e)}"
            )

    # 2. Bulk parse tasks from draft
    draft = None
    if req.draft_id:
        draft = db.get_draft_by_id(req.draft_id)
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft #{req.draft_id} not found."
            )
    else:
        draft = db.get_latest_draft(target_chat_id, user_id)
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No draft found to parse tasks from. Specify a title or generate a plan draft."
            )

    parsed_tasks = parse_tasks_from_markdown(draft.content)
    if not parsed_tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No task items found in the draft. Format should include '- [ ] Task description'."
        )

    created_issues = []
    failed_tasks = []

    first_line = draft.content.splitlines()[0] if draft.content else "Draft Plan"

    for task_title in parsed_tasks:
        try:
            issue = await github_client.create_github_issue(
                title=task_title,
                body=f"Created automatically from draft project plan.\nDraft Title: {first_line}"
            )
            issue_number = issue.get("number")
            html_url = issue.get("html_url")

            db.save_lock(db.Lock(
                issue_number=issue_number,
                repo=github_client.GITHUB_PROJECT,
                status="todo"
            ))

            created_issues.append({
                "issue_number": issue_number,
                "html_url": html_url,
                "title": task_title
            })
        except Exception as e:
            logger.error(f"Failed to create task '{task_title}': {e}")
            failed_tasks.append({
                "title": task_title,
                "error": str(e)
            })

    return {
        "status": "success",
        "total_parsed": len(parsed_tasks),
        "created_count": len(created_issues),
        "created_tasks": created_issues,
        "failed_count": len(failed_tasks),
        "failed_tasks": failed_tasks
    }
